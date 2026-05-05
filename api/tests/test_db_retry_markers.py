# -*- coding: utf-8 -*-
"""连接重试判定（TDD 锚点）：DNS 抖动与 MySQL 重启导致的拒绝连接须识别为可重试。"""

from app.db import _mysql_connect_retryable, _mysql_dns_transient


def test_retry_on_connection_refused_111():
    msg = "Can't connect to MySQL server on 'mysql' ([Errno 111] Connection refused)"
    assert _mysql_connect_retryable(msg)


def test_retry_on_dns_eagain():
    msg = "Can't connect to MySQL server on 'mysql' ([Errno -3] Temporary failure in name resolution)"
    assert _mysql_connect_retryable(msg)
    assert _mysql_dns_transient(msg)


def test_retry_on_name_not_known():
    msg = "Can't connect to MySQL server on 'mysql' ([Errno -2] Name or service not known)"
    assert _mysql_connect_retryable(msg)


def test_no_retry_on_empty_message():
    assert not _mysql_connect_retryable("")
