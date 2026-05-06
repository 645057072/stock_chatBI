# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

import os
import re
import socket
import time

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from app.config import get_settings

_engine: Engine | None = None

# 纯 IPv4 字面量（用于识别「固化 IP」路径）
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _mysql_dns_transient(msg: str) -> bool:
    """嵌入式 DNS（127.0.0.11）瞬时失败：含 EAI_AGAIN(-3)、NOTFOUND(-2) 等。"""
    if not msg:
        return False
    markers = (
        "Name or service not known",
        "Temporary failure in name resolution",
        "[Errno -3]",
        "[Errno -2]",
    )
    return any(m in msg for m in markers)


def _mysql_connect_retryable(msg: str) -> bool:
    """MySQL 进程重启或 DNS 抖动时，同一主机/port 可稍后重试。"""
    if not msg:
        return False
    if _mysql_dns_transient(msg):
        return True
    return "Connection refused" in msg or "[Errno 111]" in msg


def _getaddrinfo_ipv4_retry(host: str, port: int, attempts: int = 6):
    """解析 IPv4，嵌入 DNS 抖动时短暂重试。"""
    last: OSError | None = None
    for i in range(attempts):
        try:
            infos = socket.getaddrinfo(
                host, port, socket.AF_INET, socket.SOCK_STREAM
            )
            return infos[0][4][0]
        except OSError as ex:
            last = ex
            if i + 1 < attempts:
                time.sleep(0.25)
    assert last is not None
    raise last


def _mysql_connection():
    """每次新建 TCP；Docker DNS 瞬时失败重试 + A/B 互补回退。"""
    s = get_settings()
    port = int(s.mysql_port)
    kw = dict(
        port=port,
        user=s.mysql_user,
        password=s.mysql_password,
        database=s.mysql_database,
        connect_timeout=30,
        charset="utf8mb4",
    )
    host = s.mysql_host
    # 仅内置 Compose 时在环境中设为 mysql；外置 RDS 勿配置此项，避免误连容器服务名
    dns_name = (os.environ.get("CHATBI_MYSQL_DNS_NAME") or "").strip()

    # MySQL 容器 OOM/崩溃重启时会出现 Connection refused，拉长窗口优于单次失败
    max_attempts = 40
    sleep_s = 0.5
    last_exc: pymysql.err.OperationalError | None = None
    for attempt in range(max_attempts):
        try:
            return pymysql.connect(host=host, **kw)
        except pymysql.err.OperationalError as e:
            if e.args[0] != 2003:
                raise
            msg_e = str(e.args[1]) if len(e.args) > 1 else ""
            last_exc = e
            if attempt < max_attempts - 1 and _mysql_connect_retryable(msg_e):
                time.sleep(sleep_s)
                continue
            break

    assert last_exc is not None
    e = last_exc
    msg = str(e.args[1]) if len(e.args) > 1 else ""

    # B：配置为 IPv4 时出现 No route to host（常见于错误固化的网桥 IP）→ 改连 Compose 服务名
    if (
        dns_name
        and _IPV4.match(host)
        and "No route to host" in msg
        and dns_name != host
    ):
        return pymysql.connect(host=dns_name, **kw)

    # A：解析失败（含瞬时 EAI_AGAIN）→ 先试服务名再试 IPv4
    if dns_name and _mysql_dns_transient(msg):
        if dns_name != host:
            try:
                return pymysql.connect(host=dns_name, **kw)
            except pymysql.err.OperationalError as e2:
                if e2.args[0] != 2003:
                    raise
                msg2 = str(e2.args[1]) if len(e2.args) > 1 else ""
                if not _mysql_dns_transient(msg2):
                    raise
        try:
            ip = _getaddrinfo_ipv4_retry(dns_name, port)
        except OSError:
            raise e
        if ip == host:
            raise e
        return pymysql.connect(host=ip, **kw)

    raise last_exc


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        # QueuePool + pre_ping：高并发下复连路与断线检测；不改变 SQL 语义
        _engine = create_engine(
            "mysql+pymysql://",
            creator=_mysql_connection,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
        )
    return _engine
