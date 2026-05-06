# -*- coding: utf-8 -*-
"""密码哈希与校验（直接使用 bcrypt，避免 passlib 与 bcrypt>=4.1 不兼容）。"""

from __future__ import annotations

import bcrypt


def hash_password(plain: str) -> str:
    # 调用方需保证 UTF-8 字节长度 <= 72（见 RegisterBody / LoginBody 校验）
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def _hash_to_bcrypt_bytes(hashed: str | bytes | memoryview | None) -> bytes | None:
    """将库中读出的 password_hash 转为 bcrypt.checkpw 所需 bytes。"""
    if hashed is None:
        return None
    if isinstance(hashed, memoryview):
        hashed = hashed.tobytes()
    if isinstance(hashed, bytes):
        return hashed if hashed.strip() else None
    if isinstance(hashed, str):
        s = hashed.strip()
        if not s:
            return None
        return s.encode("utf-8")
    return None


def verify_password(plain: str, hashed: str | bytes | memoryview | None) -> bool:
    try:
        h = _hash_to_bcrypt_bytes(hashed)
        if h is None:
            return False
        return bcrypt.checkpw(plain.encode("utf-8"), h)
    except (ValueError, TypeError, UnicodeEncodeError):
        return False
