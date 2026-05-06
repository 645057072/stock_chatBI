# -*- coding: utf-8 -*-
"""TDD：exc_sql 入参须拒绝注入与多语句，放行合法只读查询。"""

import pytest

from app.sql_guard import validate_exc_sql, validate_exc_sql_or_raise


def test_allows_simple_select():
    ok, msg = validate_exc_sql("SELECT 1 AS x")
    assert ok and msg == ""


def test_allows_with_cte():
    ok, msg = validate_exc_sql(
        "WITH t AS (SELECT 1 AS a) SELECT * FROM t"
    )
    assert ok


def test_allows_leading_comment_select():
    ok, msg = validate_exc_sql("-- hi\nSELECT 1")
    assert ok


def test_rejects_multi_statement():
    ok, msg = validate_exc_sql("SELECT 1; DROP TABLE stock_daily")
    assert not ok
    assert "分号" in msg or "多条" in msg


def test_rejects_insert():
    ok, msg = validate_exc_sql("INSERT INTO app_users VALUES (1,'a','b')")
    assert not ok


def test_rejects_into_outfile():
    ok, msg = validate_exc_sql(
        "SELECT * FROM stock_daily INTO OUTFILE '/tmp/x'"
    )
    assert not ok


def test_rejects_empty():
    assert validate_exc_sql("")[0] is False
    assert validate_exc_sql("   ; ")[0] is False


def test_or_raise_raises():
    with pytest.raises(ValueError, match="SELECT|WITH"):
        validate_exc_sql_or_raise("DELETE FROM stock_daily")
