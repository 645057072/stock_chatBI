# -*- coding: utf-8 -*-
"""
TDD：Stock 脚本 MySQL 参数须来自环境变量（与 Docker / .env 一致）。
"""

import chatbi_mysql_env


def test_stock_mysql_params_ecs_docker_compose(monkeypatch):
    """模拟 ECS Docker：compose 注入 CHATBI_MYSQL_HOST=mysql、端口 3309。"""
    monkeypatch.setenv("CHATBI_MYSQL_HOST", "mysql")
    monkeypatch.setenv("CHATBI_MYSQL_PORT", "3309")
    monkeypatch.setenv("MYSQL_USER", "root")
    monkeypatch.setenv("MYSQL_PASSWORD", "prod_secret_from_env")
    monkeypatch.setenv("MYSQL_DATABASE", "chat_bi_case")

    h, p, u, pw, db = chatbi_mysql_env.stock_mysql_params()
    assert h == "mysql"
    assert p == 3309
    assert u == "root"
    assert pw == "prod_secret_from_env"
    assert db == "chat_bi_case"


def test_fallback_mysql_host_when_chatbi_unset(monkeypatch):
    monkeypatch.delenv("CHATBI_MYSQL_HOST", raising=False)
    monkeypatch.delenv("CHATBI_MYSQL_PORT", raising=False)
    monkeypatch.setenv("MYSQL_HOST", "192.168.1.10")
    monkeypatch.setenv("MYSQL_PORT", "3309")

    h, p, _, _, _ = chatbi_mysql_env.stock_mysql_params()
    assert h == "192.168.1.10"
    assert p == 3309


def test_password_from_env_not_hardcoded_placeholder(monkeypatch):
    monkeypatch.setenv("MYSQL_PASSWORD", "only_from_dotenv")
    _, _, _, pw, _ = chatbi_mysql_env.stock_mysql_params()
    assert pw == "only_from_dotenv"
