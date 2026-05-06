# -*- coding: utf-8 -*-
"""TDD：网关模板须含可注入占位符，且保留 Nginx 原生 $host 等变量（envsubst 仅替换列出的键）。"""

from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_nginx_template_has_envsubst_placeholders():
    p = _repo_root() / "deploy" / "nginx.conf.template"
    assert p.is_file(), "缺少 deploy/nginx.conf.template"
    text = p.read_text(encoding="utf-8")
    assert "${CHATBI_API_UPSTREAM}" in text
    assert "${CHATBI_NGINX_PROXY_TIMEOUT}" in text
    assert "$host" in text
    assert "proxy_pass http://chatbi_api/" in text


def test_nginx_entrypoint_exists():
    p = _repo_root() / "deploy" / "nginx-entrypoint.sh"
    assert p.is_file()
    body = p.read_text(encoding="utf-8")
    assert "envsubst" in body
    assert "CHATBI_API_UPSTREAM" in body
