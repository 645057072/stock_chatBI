# -*- coding: utf-8 -*-
"""项目根目录与静态资源目录（与助手脚本 IMAGE_DIR 环境变量一致）。"""

import os
from pathlib import Path


def project_root() -> Path:
    """向上查找包含 assistant_stock_bot-5.py 的目录（兼容源码与 Docker）。"""
    p = Path(__file__).resolve().parent
    for _ in range(6):
        if (p / "assistant_stock_bot-5.py").exists():
            return p
        p = p.parent
    raise RuntimeError("找不到 assistant_stock_bot-5.py")


def image_show_dir() -> str:
    custom = os.getenv("STOCK_BOT_IMAGE_DIR")
    if custom:
        return custom.strip()
    return str((project_root() / "image_show").resolve())
