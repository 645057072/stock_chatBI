# -*- coding: utf-8 -*-
"""基于 Redis 的固定窗口限流。"""

import time

from redis import Redis


def allow(redis: Redis, key: str, limit: int, window_seconds: int = 60) -> bool:
    """
    在 window_seconds 内允许最多 limit 次。
    返回 True 表示未超限，False 表示已拒绝。
    """
    bucket = int(time.time() // window_seconds)
    rk = f"{key}:{bucket}"
    n = redis.incr(rk)
    if n == 1:
        redis.expire(rk, window_seconds * 2)
    return n <= limit
