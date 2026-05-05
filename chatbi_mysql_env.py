# -*- coding: utf-8 -*-
"""
Stock 脚本与 FastAPI 编排共用的 MySQL 参数（一律从环境变量读取，与 .env / compose 一致）。

优先级与 api/app/config.py 对齐：CHATBI_MYSQL_HOST / CHATBI_MYSQL_PORT 优先于 MYSQL_HOST / MYSQL_PORT。
"""

from __future__ import annotations

import os


def stock_mysql_params() -> tuple[str, int, str, str, str]:
    """返回 (host, port, user, password, database)，每次调用重新读取 os.environ。"""
    host = os.getenv("CHATBI_MYSQL_HOST") or os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("CHATBI_MYSQL_PORT") or os.getenv("MYSQL_PORT", "3309"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "AAAAa@321")
    database = os.getenv("MYSQL_DATABASE", "chat_bi_case")
    return host, port, user, password, database
