# -*- coding: utf-8 -*-
"""
使用 tushare 拉取指定股票日线行情，按交易日期升序合并到单个工作表并导出为 xlsx。
需设置环境变量 TUSHARE_TOKEN。
"""
from __future__ import annotations

import os
from datetime import date

import pandas as pd
import tushare as ts

# 股票代码与名称（tushare ts_code 格式）
STOCKS: list[tuple[str, str]] = [
    ("600519.SH", "贵州茅台"),
    ("600271.SH", "航天信息"),
    ("000858.SZ", "五粮液"),
    ("000776.SZ", "广发证券"),
    ("688981.SH", "中芯国际"),
    ("002594.SZ", "比亚迪"),
    ("000063.SZ", "中兴通讯"),
]

START_DATE = "20200101"
OUTPUT_FILE = "stock_history.xlsx"
SHEET_NAME = "历史行情"


def main() -> None:
    token = os.environ.get("TUSHARE_TOKEN")
    if not token:
        raise RuntimeError("请先设置环境变量 TUSHARE_TOKEN")

    ts.set_token(token)
    pro = ts.pro_api()

    end = date.today().strftime("%Y%m%d")

    frames: list[pd.DataFrame] = []
    for ts_code, name in STOCKS:
        df = pro.daily(ts_code=ts_code, start_date=START_DATE, end_date=end)
        if df is None or df.empty:
            continue
        df = df.copy()
        df.insert(0, "股票名称", name)
        frames.append(df)

    if not frames:
        raise RuntimeError("未获取到任何行情数据，请检查 token 权限与网络")

    out = pd.concat(frames, ignore_index=True)
    # trade_date 为字符串 YYYYMMDD，按时间升序
    out = out.sort_values(["trade_date", "ts_code"], ascending=True).reset_index(drop=True)

    out.to_excel(OUTPUT_FILE, sheet_name=SHEET_NAME, index=False, engine="openpyxl")
    print(f"已保存: {OUTPUT_FILE}，共 {len(out)} 行")


if __name__ == "__main__":
    main()
