# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        url = URL.create(
            drivername="mysql+pymysql",
            username=s.mysql_user,
            password=s.mysql_password,
            host=s.mysql_host,
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
