# -*- coding: utf-8 -*-
"""TDD：应用 MySQL 引擎使用连接池以利于并发，并保持 creator 直连逻辑不变。"""

from sqlalchemy.pool import QueuePool

from app.db import get_engine


def test_engine_uses_queue_pool():
    eng = get_engine()
    try:
        assert isinstance(eng.pool, QueuePool)
    finally:
        eng.dispose()
