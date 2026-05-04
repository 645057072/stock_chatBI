# -*- coding: utf-8 -*-
"""MySQL 连接（用户表）。"""

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, URL
from sqlalchemy.pool import NullPool

from app.config import get_settings

_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        s = get_settings()
        # 使用服务名 mysql，勿在启动时固化 IPv4：编排中网桥 IP 会变，固化后连接池重建易出现 timed out
        # NullPool：每次 borrow 新建 TCP，避免失效连接留在池中触发 InvalidatePoolError，且每次解析主机名
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
            poolclass=NullPool,
            connect_args={"connect_timeout": 30},
        )
    return _engine
