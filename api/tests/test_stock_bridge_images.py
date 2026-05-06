# -*- coding: utf-8 -*-
"""TDD：Markdown 图表 URL 须对应 FastAPI /static 挂载（文件直接在挂载根下）。"""

from app.stock_bridge import rewrite_markdown_images


def test_rewrite_maps_image_show_to_static_root():
    md = "![图表](image_show/stock_123.png)"
    out = rewrite_markdown_images(md, "/api/static")
    assert out == "![图表](/api/static/stock_123.png)"
    assert "image_show" not in out


def test_rewrite_strips_trailing_slash_on_prefix():
    md = "![图](image_show/a.png)"
    out = rewrite_markdown_images(md, "/api/static/")
    assert out == "![图](/api/static/a.png)"
