# -*- coding: utf-8 -*-
"""TDD：网关 HTML 错误页须识别并转为中文提示，避免当作 Markdown 渲染。"""

from app.http_user_message import (
    MSG_HTML_GATEWAY,
    looks_like_html_gateway_page,
    sanitize_llm_reply_if_gateway_html,
)


def test_looks_like_nginx_502_page():
    html = (
        "<html><head><title>502 Bad Gateway</title></head>"
        "<body><center><h1>502 Bad Gateway</h1></center>"
        "<hr><center>nginx/1.27.3</center></body></html>"
    )
    assert looks_like_html_gateway_page(html) is True


def test_sanitize_replaces_gateway_html_with_zh():
    html = (
        "<html><head><title>502 Bad Gateway</title></head><body>"
        "<h1>502 Bad Gateway</h1><center>nginx/1.27.3</center></body></html>"
    )
    assert sanitize_llm_reply_if_gateway_html(html) == MSG_HTML_GATEWAY


def test_normal_assistant_text_not_sanitized():
    text = "贵州茅台近一年收盘价走势如下（示例）。"
    assert sanitize_llm_reply_if_gateway_html(text) == text


def test_short_string_not_flagged():
    assert looks_like_html_gateway_page("<html>502") is False
