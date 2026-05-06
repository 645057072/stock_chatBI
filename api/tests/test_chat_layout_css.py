# -*- coding: utf-8 -*-
"""TDD：对话页须为三列同级 flex（侧栏 20% | 主区 flex:1 | 服务能力 20%），禁止 centerWrap 嵌套导致右侧缝隙。"""

from pathlib import Path


def _css_text() -> str:
    root = Path(__file__).resolve().parents[2]
    p = root / "web" / "src" / "pages" / "ChatPage.module.css"
    return p.read_text(encoding="utf-8")


def test_no_center_wrap_nested_gap_pattern():
    css = _css_text()
    assert ".centerWrap" not in css, "应移除 centerWrap，避免 main 60%+cap 20% 仅占父级 80% 留出空白"


def test_three_column_flex_under_layout():
    css = _css_text()
    assert ".layout {" in css
    layout_block = css.split(".layout {", 1)[1].split("}", 1)[0]
    assert "flex-direction: row" in layout_block or "display: flex" in layout_block

    main_block = css.split(".main {", 1)[1].split("}", 1)[0]
    assert "flex: 1 1 0" in main_block or "flex:1 1 0" in main_block.replace(" ", "")

    cap_block = css.split(".capPanel {", 1)[1].split("}", 1)[0]
    assert "flex: 0 0 20%" in cap_block
    assert "max-width: 20%" in cap_block


def test_bubble_bot_allows_flex_shrink():
    css = _css_text()
    bubble_block = css.split(".bubbleBot {", 1)[1].split("}", 1)[0]
    assert "min-width: 0" in bubble_block
