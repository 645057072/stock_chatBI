# -*- coding: utf-8 -*-
"""股票查询结果展示：列名中文化、判断 stock_name 是否仅为代码（需按 ts_code 解析简称）。"""

from __future__ import annotations

import pandas as pd

# stock_daily 及工具输出常用列 -> 中文表头
DISPLAY_COL_ZH: dict[str, str] = {
    "trade_date": "交易日期",
    "stock_name": "股票名称",
    "ts_code": "证券代码",
    "close_price": "收盘价",
    "open_price": "开盘价",
    "high_price": "最高价",
    "low_price": "最低价",
    "pre_close": "昨收价",
    "price_change": "涨跌额",
    "pct_chg": "涨跌幅(%)",
    "vol": "成交量(手)",
    "amount": "成交额(千元)",
    "boll_mid": "布林中轨",
    "boll_upper": "布林上轨",
    "boll_lower": "布林下轨",
    "boll_signal": "布林带信号",
    "predict_date": "预测日期",
    "predict_close_price": "预测收盘价",
    "month": "月份",
    "avg_close": "平均收盘价",
    "close": "收盘价",
}


def stock_name_needs_resolve(name: object, ts_code: str) -> bool:
    """
    若 stock_name 为空、等于代码前缀、或与 6 位数字代码混淆，则需要用 ts_code 拉取证券简称。
    """
    if name is None:
        return True
    if isinstance(name, float) and pd.isna(name):
        return True
    s = str(name).strip()
    if not s:
        return True
    tc = str(ts_code).strip().upper()
    if not tc:
        return True
    prefix = tc.split(".", 1)[0] if "." in tc else tc
    if s == tc or s.upper() == tc or s == prefix:
        return True
    if s.isdigit() and len(s) == 6:
        return True
    return False


def rename_dataframe_columns_zh(df: pd.DataFrame) -> pd.DataFrame:
    """将已知英文列名替换为中文（仅映射 DISPLAY_COL_ZH 中存在的列）。"""
    mapping = {c: DISPLAY_COL_ZH[c] for c in df.columns if c in DISPLAY_COL_ZH}
    return df.rename(columns=mapping) if mapping else df


def axis_label_zh(column_name: str) -> str:
    """坐标轴标签：已知列用中文，否则保留原列名。"""
    return DISPLAY_COL_ZH.get(column_name, column_name)
