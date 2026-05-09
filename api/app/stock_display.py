# -*- coding: utf-8 -*-
"""股票查询结果展示：列名中文化、判断 stock_name 是否仅为代码（需按 ts_code 解析简称）。"""

from __future__ import annotations

import pandas as pd

# 证券代码 -> 常用中文简称（与主流行情软件/Tushare 证券简称一致）。
# 用于纠偏 stock_daily 中 stock_name 与 ts_code 错配（例如 600519 被标成「航天信息」）。
CANONICAL_TS_CODE_TO_STOCK_NAME_ZH: dict[str, str] = {
    "600519.SH": "贵州茅台",
    "600271.SH": "航天信息",
    "000858.SZ": "五粮液",
    "000776.SZ": "广发证券",
    "688981.SH": "中芯国际",
    "002594.SZ": "比亚迪",
    "000063.SZ": "中兴通讯",
}

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
    "avg_daily_vol_hand": "本月日均成交量(手)",
    "trading_days_in_month": "本月交易日数",
}


def canonical_stock_name_for_ts_code(ts_code: object) -> str | None:
    """若 ts_code 在权威表中有定义，返回对应中文简称，否则 None。"""
    if ts_code is None:
        return None
    tc = str(ts_code).strip().upper()
    return CANONICAL_TS_CODE_TO_STOCK_NAME_ZH.get(tc)


def merge_canonical_into_ts_code_name_map(ts_to_name: dict[str, str]) -> dict[str, str]:
    """对已有 ts_code->stock_name 映射用权威表覆盖（仅覆盖 map 中已出现的 ts_code）。"""
    out = {str(k).strip().upper(): str(v) for k, v in ts_to_name.items()}
    for tc, nm in CANONICAL_TS_CODE_TO_STOCK_NAME_ZH.items():
        if tc in out:
            out[tc] = nm
    return out


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


def prepare_dataframe_for_markdown(df: pd.DataFrame) -> pd.DataFrame:
    """
    导出 Markdown 表格前格式化数值：避免科学计数法；成交量列用千分位整数样式；
    价格类保留适量小数（转为可读字符串，不改变原始查询语义）。
    """
    out = df.copy()
    for col in list(out.columns):
        ser = out[col]
        if not pd.api.types.is_numeric_dtype(ser):
            continue
        key = str(col).lower()

        def fmt_cell(v: object, k: str = key) -> object:
            if pd.isna(v):
                return pd.NA
            fv = float(v)
            if k == "vol":
                return f"{int(round(fv)):,}"
            if k == "pct_chg":
                s = f"{fv:.6f}".rstrip("0").rstrip(".")
                return s if s else "0"
            s = f"{fv:,.6f}".rstrip("0").rstrip(".")
            return s if s else "0"

        out[col] = ser.map(fmt_cell)
    return out


def rename_dataframe_columns_zh(df: pd.DataFrame) -> pd.DataFrame:
    """将已知英文列名替换为中文（仅映射 DISPLAY_COL_ZH 中存在的列）。"""
    mapping = {c: DISPLAY_COL_ZH[c] for c in df.columns if c in DISPLAY_COL_ZH}
    return df.rename(columns=mapping) if mapping else df


def axis_label_zh(column_name: str) -> str:
    """坐标轴标签：已知列用中文，否则保留原列名。"""
    return DISPLAY_COL_ZH.get(column_name, column_name)


def resolve_dataframe_column(df: pd.DataFrame, logical_name: str) -> str | None:
    """按逻辑列名（不区分大小写）解析 DataFrame 中的实际列名。"""
    m = {str(c).lower(): c for c in df.columns}
    return m.get(logical_name.lower())


def normalize_ts_code_series(s: pd.Series) -> pd.Series:
    """统一证券代码格式，避免 TS_CODE 大小写或空格导致误判为单只股票。"""
    return s.astype(str).str.strip().str.upper()


def comparison_numeric_describe_blocks(
    df: pd.DataFrame,
    ts_column: str | None,
    numeric_cols: list[str],
) -> list[tuple[str, pd.DataFrame]]:
    """
    多证券对比：按 ts_code 分组分别 describe；
    仅一只证券或未提供 ts 列时，返回整张表一段描述。
    """
    if not numeric_cols:
        return []
    sub_num = df[numeric_cols]
    if ts_column is None or ts_column not in df.columns:
        return [("", sub_num.describe().round(6))]
    norm = normalize_ts_code_series(df[ts_column])
    if norm.nunique(dropna=False) <= 1:
        return [("", sub_num.describe().round(6))]
    out: list[tuple[str, pd.DataFrame]] = []
    df_work = df.copy()
    df_work["_ts_norm"] = norm
    sn_actual = resolve_dataframe_column(df_work, "stock_name")
    for code, g in df_work.groupby("_ts_norm", sort=True):
        title_code = str(code)
        sn = ""
        if sn_actual and sn_actual in g.columns and g[sn_actual].notna().any():
            sn = str(g[sn_actual].iloc[-1]).strip()
        title = f"{sn} ({title_code})" if sn else title_code
        out.append((title, g[numeric_cols].describe().round(6)))
    return out


def format_comparison_describe_markdown(blocks: list[tuple[str, pd.DataFrame]]) -> str:
    """将分组 describe 转为 Markdown（列名中文化）。"""
    if not blocks:
        return "无可用于描述统计的数值列。"
    parts: list[str] = []
    for title, desc in blocks:
        zh = rename_dataframe_columns_zh(prepare_dataframe_for_markdown(desc.copy()))
        md = zh.to_markdown(tablefmt="github")
        parts.append(f"#### {title}\n\n{md}" if title else md)
    return "\n\n".join(parts)
