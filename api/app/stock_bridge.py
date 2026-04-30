# -*- coding: utf-8 -*-
"""动态加载项目根目录下的 assistant_stock_bot-5.py（文件名含连字符，无法用常规 import）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from app.paths import project_root

_mod = None


def get_bot_module():
    global _mod
    if _mod is None:
        root = project_root()
        bot_path = root / "assistant_stock_bot-5.py"
        spec = importlib.util.spec_from_file_location("assistant_stock_bot_v5", bot_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("无法加载 assistant_stock_bot-5.py")
        _mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_mod)
    return _mod


def run_agent_turn(messages: list) -> list:
    return get_bot_module().run_agent_turn(messages)


def rewrite_markdown_images(text: str, static_prefix: str) -> str:
    """将助手返回的相对路径图片改为经网关访问的绝对路径前缀。"""
    if not text:
        return text
    return text.replace("](image_show/", f"]({static_prefix}/image_show/")
