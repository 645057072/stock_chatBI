# -*- coding: utf-8 -*-
"""登录链路：password_hash 在驱动下可能为 bytes/memoryview，校验须稳定且不抛未捕获异常。"""

from app.auth_util import hash_password, verify_password


def test_verify_accepts_str_hash():
    h = hash_password("secret12345")
    assert verify_password("secret12345", h) is True
    assert verify_password("wrong", h) is False


def test_verify_accepts_bytes_hash():
    h = hash_password("secret12345")
    assert verify_password("secret12345", h.encode("ascii")) is True


def test_verify_accepts_memoryview_hash():
    h = hash_password("secret12345")
    raw = h.encode("ascii")
    assert verify_password("secret12345", memoryview(raw)) is True


def test_verify_invalid_hash_no_throw():
    assert verify_password("any", "") is False
    assert verify_password("any", "plaintext-no-bcrypt") is False
    assert verify_password("any", None) is False
