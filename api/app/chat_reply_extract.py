# -*- coding: utf-8 -*-
"""从 qwen-agent 增量消息中提取 assistant 正文（字符串或多段 content）。"""

from __future__ import annotations

from typing import Any


def content_to_plain_text(content: Any) -> str:
    """将助手消息的 content 转为纯文本（兼容字符串与多段列表结构）。"""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        for key in ("text", "content", "input", "output"):
            v = content.get(key)
            if isinstance(v, str) and v.strip():
                return v
            if isinstance(v, list):
                sub = content_to_plain_text(v).strip()
                if sub:
                    return sub
        v2 = content.get("value")
        if isinstance(v2, str) and v2.strip():
            return v2
        return ""
    if isinstance(content, list):
        parts: list[str] = []
        for p in content:
            if isinstance(p, str):
                parts.append(p)
            elif isinstance(p, dict):
                picked = False
                for key in ("text", "content", "input", "output"):
                    v = p.get(key)
                    if isinstance(v, str) and v.strip():
                        parts.append(v)
                        picked = True
                        break
                if not picked:
                    v2 = p.get("value")
                    if isinstance(v2, str) and v2.strip():
                        parts.append(v2)
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return str(content)


def extract_assistant_text(delta: list[Any]) -> str:
    """从助手增量消息列表中提取所有 assistant 角色的可见文本。"""
    chunks: list[str] = []
    for item in delta:
        if not isinstance(item, dict):
            continue
        if item.get("role") != "assistant":
            continue
        text = content_to_plain_text(item.get("content")).strip()
        if text:
            chunks.append(text)
    merged = "\n\n".join(chunks).strip()
    return merged if merged else "（无文本回复）"
