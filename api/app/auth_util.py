# -*- coding: utf-8 -*-
"""密码哈希与校验（直接使用 bcrypt，避免 passlib 与 bcrypt>=4.1 不兼容）。"""

import bcrypt


def hash_password(plain: str) -> str:
    # 调用方需保证 UTF-8 字节长度 <= 72（见 RegisterBody / LoginBody 校验）
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False
