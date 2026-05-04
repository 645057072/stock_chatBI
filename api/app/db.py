# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

import logging
import socket

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

from app.config import get_settings

_engine: Engine | None = None
_log = logging.getLogger("uvicorn.error")


def _tcp_ipv4_for_mysql_host(host: str) -> str:
    """将主机名解析为 IPv4，避免连接池重建时对服务名二次 DNS 解析间歇失败（gaierror -2）。"""
    h = (host or "").strip()
    if not h:
        return h
    try:
        socket.inet_aton(h)
        return h
    except OSError:
        pass
    try:
        infos = socket.getaddrinfo(h, None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            ip = infos[0][4][0]
            _log.info("MySQL 主机 %s 解析为 IPv4 %s（连接串使用 IP，减轻 Docker DNS 波动）", h, ip)
            return ip
    except OSError as e:
        _log.warning("MySQL 主机 %s IPv4 解析失败，仍使用主机名字符串：%s", h, e)
    return h


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        connect_host = _tcp_ipv4_for_mysql_host(s.mysql_host)
        url = URL.create(
            drivername="mysql+pymysql",
            username=s.mysql_user,
            password=s.mysql_password,
            host=connect_host,
            port=s.mysql_port,
            database=s.mysql_database,
            query={"charset": "utf8mb4"},
        )
        _engine = create_engine(
            url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            connect_args={"connect_timeout": 10},
        )
    return _engine
