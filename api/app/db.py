# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

import os
import re
import socket

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine: Engine | None = None

# 纯 IPv4 字面量（用于识别「固化 IP」路径）
_IPV4 = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")


def _mysql_connection():
    """每次新建 TCP；针对 Docker ECS 上两类错误做一次性互补重试（A/B）。"""
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

    try:
        return pymysql.connect(host=host, **kw)
    except pymysql.err.OperationalError as e:
        if e.args[0] != 2003:
            raise
        msg = str(e.args[1]) if len(e.args) > 1 else ""

        # B：配置为 IPv4 时出现 No route to host（常见于错误固化的网桥 IP）→ 改连 Compose 服务名
        if (
            dns_name
            and _IPV4.match(host)
            and "No route to host" in msg
            and dns_name != host
        ):
            return pymysql.connect(host=dns_name, **kw)

        # A：主机名无法解析 → 先试服务名再试 IPv4（依赖 dns_name，RDS 场景不配置）
        if dns_name and "Name or service not known" in msg:
            if dns_name != host:
                try:
                    return pymysql.connect(host=dns_name, **kw)
                except pymysql.err.OperationalError as e2:
                    if e2.args[0] != 2003:
                        raise
                    msg2 = str(e2.args[1]) if len(e2.args) > 1 else ""
                    if "Name or service not known" not in msg2:
                        raise
            try:
                infos = socket.getaddrinfo(
                    dns_name, port, socket.AF_INET, socket.SOCK_STREAM
                )
                ip = infos[0][4][0]
            except OSError:
                raise e
            if ip == host:
                raise e
            return pymysql.connect(host=ip, **kw)

        raise


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            "mysql+pymysql://",
            creator=_mysql_connection,
            poolclass=NullPool,
        )
    return _engine
