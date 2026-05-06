# -*- coding: utf-8 -*-
"""TDD：股票展示列名与证券简称解析规则。"""

import pandas as pd

from app.stock_display import (
    axis_label_zh,
    rename_dataframe_columns_zh,
    stock_name_needs_resolve,
)


def test_stock_name_needs_resolve_when_numeric_or_code():
    assert stock_name_needs_resolve("600519", "600519.SH") is True
    assert stock_name_needs_resolve("600519.SH", "600519.SH") is True
    assert stock_name_needs_resolve("", "600519.SH") is True
    assert stock_name_needs_resolve(None, "600519.SH") is True


def test_stock_name_needs_resolve_when_real_name():
    assert stock_name_needs_resolve("贵州茅台", "600519.SH") is False


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
