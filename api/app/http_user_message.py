# -*- coding: utf-8 -*-
"""识别网关错误页 HTML，转为对用户可读的中文提示（助手回复 / 前端错误文案共用逻辑）。"""

from __future__ import annotations

import re

# 与前端 api.ts 中文案保持语义一致
MSG_HTML_GATEWAY = (
    "网关暂时无法连接后端服务，请稍后重试；若反复出现请联系管理员检查 API 与 Nginx 状态。"
)


_html_tag_re = re.compile(r"<html\b", re.IGNORECASE)
_doctype_re = re.compile(r"<!doctype\s+html", re.IGNORECASE)


def looks_like_html_gateway_page(text: str) -> bool:
    """判断是否像 Nginx/网关返回的 HTML 错误页（502/504 等）。"""
    if not text or not isinstance(text, str):
        return False
    if len(text.strip()) < 24:
        return False
    lower = text.lower()
    if not (_html_tag_re.search(text) or _doctype_re.search(text)):
        return False
    if "502" in text or "504" in text:
        return True
    if "bad gateway" in lower or "gateway time-out" in lower or "gateway timeout" in lower:
        return True
    if "nginx/" in lower and ("502" in text or "504" in text or "bad gateway" in lower):
        return True
    return False


def sanitize_llm_reply_if_gateway_html(text: str) -> str:
    """若助手输出误混入网关 HTML，替换为固定中文说明。"""
    if looks_like_html_gateway_page(text):
        return MSG_HTML_GATEWAY
    return text
