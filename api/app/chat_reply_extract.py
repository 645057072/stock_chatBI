# -*- coding: utf-8 -*-
"""从 qwen-agent 增量消息中提取 assistant 正文（字符串或多段 content）。"""

from __future__ import annotations

from typing import Any


def _dict_media_to_markdown(d: dict) -> str:
    """ContentItem 序列化后可能仅有 image/file 等字段，转成 Markdown 便于前端展示。"""
    img = d.get("image")
    if isinstance(img, str) and img.strip():
        return f"![]({img.strip()})"
    fn = d.get("file")
    if isinstance(fn, str) and fn.strip():
        return f"[附件]({fn.strip()})"
    return ""


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
        media = _dict_media_to_markdown(content)
        if media:
            return media
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
                        media = _dict_media_to_markdown(p)
                        if media:
                            parts.append(media)
            else:
                parts.append(str(p))
        return "\n".join(parts)
    return str(content)


def _assistant_visible_blocks(item: dict) -> list[str]:
    """
    组装单条 assistant 消息的可见块。
    Qwen3 等模型可能将正文放在 reasoning_content，content 为空或仅有工具调用占位。
    """
    seen: set[str] = set()
    out: list[str] = []
    for key in ("content", "reasoning_content"):
        raw = item.get(key)
        t = content_to_plain_text(raw).strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


def extract_assistant_text(delta: list[Any]) -> str:
    """从助手增量消息列表中提取所有 assistant 角色的可见文本。"""
    chunks: list[str] = []
    for item in delta:
        if not isinstance(item, dict):
            continue
        if item.get("role") != "assistant":
            continue
        blocks = _assistant_visible_blocks(item)
        if blocks:
            chunks.append("\n\n".join(blocks))
    merged = "\n\n".join(chunks).strip()
    return merged if merged else "（无文本回复）"
