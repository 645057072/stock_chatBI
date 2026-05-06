# -*- coding: utf-8 -*-

from app.chat_reply_extract import content_to_plain_text, extract_assistant_text


def test_content_to_plain_text_nested_dict():
    assert "hello" in content_to_plain_text([{"text": "hello"}, {"content": "world"}])


def test_extract_skips_empty_assistant_strings():
    delta = [
        {"role": "assistant", "content": ""},
        {"role": "assistant", "content": "   "},
    ]
    assert extract_assistant_text(delta) == "（无文本回复）"


def test_extract_merges_multiple_assistant_messages():
    delta = [
        {"role": "assistant", "content": "第一段"},
        {"role": "tool", "content": "x"},
        {"role": "assistant", "content": [{"text": "第二段"}]},
    ]
    assert "第一段" in extract_assistant_text(delta)
    assert "第二段" in extract_assistant_text(delta)


def test_extract_ignores_non_assistant():
    delta = [{"role": "user", "content": "hi"}]
    assert extract_assistant_text(delta) == "（无文本回复）"


def test_extract_assistant_dict_content():
    delta = [{"role": "assistant", "content": {"text": "来自 dict 的正文"}}]
    assert extract_assistant_text(delta) == "来自 dict 的正文"


def test_extract_assistant_reasoning_content_when_content_empty():
    """Qwen3 等模型常把可见输出放在 reasoning_content。"""
    delta = [
        {
            "role": "assistant",
            "content": "",
            "reasoning_content": "贵州茅台近一年收盘价走势如下……",
        }
    ]
    assert extract_assistant_text(delta) == "贵州茅台近一年收盘价走势如下……"


def test_extract_contentitem_image_only():
    delta = [
        {
            "role": "assistant",
            "content": [{"image": "image_show/foo.png"}],
        }
    ]
    assert "image_show/foo.png" in extract_assistant_text(delta)
    assert "![" in extract_assistant_text(delta)
