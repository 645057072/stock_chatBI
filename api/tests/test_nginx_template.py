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
    # 动态解析上游，避免 api 容器重建后旧 IP 导致 502
    assert "resolver 127.0.0.11" in text
    assert "rewrite ^/api/(.*)$ /$1 break;" not in text
    assert 'set $chatbi_upstream "${CHATBI_API_UPSTREAM}"' in text
    assert "proxy_pass http://$chatbi_upstream/;" in text
    assert "upstream chatbi_api" not in text


def test_api_location_set_upstream_before_proxy_pass():
    """set 须在 proxy_pass 之前，避免变量未初始化。"""
    p = _repo_root() / "deploy" / "nginx.conf.template"
    text = p.read_text(encoding="utf-8")
    pos = 0
    for _ in range(2):
        s = text.find("set $chatbi_upstream", pos)
        r = text.find("proxy_pass http://$chatbi_upstream/", pos)
        assert s != -1 and r != -1, "每个 server 块须含 set 与 proxy_pass"
        assert s < r
        pos = r + 10


def test_substituted_upstream_literal_nonempty():
    """模拟 envsubst 后上游片段不得为空（对应 nginx invalid URL prefix）。"""
    p = _repo_root() / "deploy" / "nginx.conf.template"
    raw = p.read_text(encoding="utf-8")
    out = raw.replace("${CHATBI_API_UPSTREAM}", "api:8000").replace(
        "${CHATBI_NGINX_PROXY_TIMEOUT}", "600s"
    )
    assert 'set $chatbi_upstream "api:8000"' in out
    assert 'proxy_pass http://$chatbi_upstream/;' in out


def test_nginx_entrypoint_exists():
    p = _repo_root() / "deploy" / "nginx-entrypoint.sh"
    assert p.is_file()
    body = p.read_text(encoding="utf-8")
    assert "envsubst" in body
    assert "CHATBI_API_UPSTREAM" in body
    assert "tr -d" in body and "\\r" in body  # 字面量 \r，去除 Windows .env 带入的 CR
    assert '[ -z "$CHATBI_API_UPSTREAM" ]' in body
