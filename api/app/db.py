# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

import pymysql
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine: Engine | None = None


def _mysql_connection():
    """每次新建 TCP，由 pymysql 解析主机名，避免过期 /etc/hosts 或固定 IP 导致 No route to host。"""
    s = get_settings()
    return pymysql.connect(
        host=s.mysql_host,
        port=int(s.mysql_port),
        user=s.mysql_user,
        password=s.mysql_password,
        database=s.mysql_database,
        connect_timeout=30,
        charset="utf8mb4",
    )


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(
            "mysql+pymysql://",
            creator=_mysql_connection,
            poolclass=NullPool,
        )
    return _engine
