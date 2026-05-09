# -*- coding: utf-8 -*-
"""TDD：股票展示列名与证券简称解析规则。"""

import pandas as pd

from app.stock_display import (
    axis_label_zh,
    canonical_stock_name_for_ts_code,
    comparison_numeric_describe_blocks,
    format_comparison_describe_markdown,
    merge_canonical_into_ts_code_name_map,
    prepare_dataframe_for_markdown,
    rename_dataframe_columns_zh,
    resolve_dataframe_column,
    stock_name_needs_resolve,
)


def test_stock_name_needs_resolve_when_numeric_or_code():
    assert stock_name_needs_resolve("600519", "600519.SH") is True
    assert stock_name_needs_resolve("600519.SH", "600519.SH") is True
    assert stock_name_needs_resolve("", "600519.SH") is True
    assert stock_name_needs_resolve(None, "600519.SH") is True


def test_stock_name_needs_resolve_when_real_name():
    assert stock_name_needs_resolve("贵州茅台", "600519.SH") is False


def test_canonical_stock_name_for_ts_code():
    assert canonical_stock_name_for_ts_code("600271.SH") == "航天信息"
    assert canonical_stock_name_for_ts_code("600519.sh") == "贵州茅台"
    assert canonical_stock_name_for_ts_code("999999.SH") is None


def test_merge_canonical_overrides_wrong_db_name():
    m = merge_canonical_into_ts_code_name_map({"600519.SH": "航天信息", "600271.SH": "航天信息"})
    assert m["600519.SH"] == "贵州茅台"
    assert m["600271.SH"] == "航天信息"


def test_rename_dataframe_columns_zh_partial():
    df = pd.DataFrame(
        {
            "trade_date": ["2026-01-01"],
            "ts_code": ["600519.SH"],
            "close_price": [100.0],
            "unknown_col": [1],
        }
    )
    out = rename_dataframe_columns_zh(df)
    assert list(out.columns) == ["交易日期", "证券代码", "收盘价", "unknown_col"]


def test_axis_label_zh_known_and_fallback():
    assert axis_label_zh("trade_date") == "交易日期"
    assert axis_label_zh("custom_metric") == "custom_metric"


def test_resolve_dataframe_column_case_insensitive():
    df = pd.DataFrame({"TS_CODE": ["600519.SH"], "Close_Price": [1.0]})
    assert resolve_dataframe_column(df, "ts_code") == "TS_CODE"
    assert resolve_dataframe_column(df, "close_price") == "Close_Price"


def test_prepare_dataframe_for_markdown_avoids_scientific_notation():
    df = pd.DataFrame({"vol": [1216390.0], "close_price": [13.5]})
    out = prepare_dataframe_for_markdown(df)
    assert "e+" not in str(out.iloc[0]["vol"]).lower()
    assert "," in str(out.iloc[0]["vol"])


def test_comparison_numeric_describe_blocks_splits_by_ts():
    df = pd.DataFrame(
        {
            "ts_code": ["688981.SH", "688981.SH", "600271.SH", "600271.SH"],
            "stock_name": ["中芯国际", "中芯国际", "航天信息", "航天信息"],
            "close_price": [10.0, 12.0, 20.0, 18.0],
        }
    )
    blocks = comparison_numeric_describe_blocks(df, "ts_code", ["close_price"])
    assert len(blocks) == 2
    titles = [b[0] for b in blocks]
    assert any("688981" in t for t in titles)
    assert any("600271" in t for t in titles)
    md = format_comparison_describe_markdown(blocks)
    assert "688981" in md or "中芯国际" in md
    assert "600271" in md or "航天信息" in md
