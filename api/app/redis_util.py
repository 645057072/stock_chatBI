# -*- coding: utf-8 -*-
"""Redis 客户端（会话、对话缓存、限流）。"""

import redis

from app.config import get_settings

_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis.from_url(get_settings().redis_url, decode_responses=True)
    return _client
