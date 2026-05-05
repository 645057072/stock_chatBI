# -*- coding: utf-8 -*-
"""
执行 schema.sql 中的建库建表（若不存在），从 tushare 拉取与导出 Excel 相同的股票日线数据，
清空 stock_daily 后全量写入 MySQL。

需环境变量 TUSHARE_TOKEN。数据库连接与 .env 中 MYSQL_* / CHATBI_MYSQL_* 一致。
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import pymysql
import tushare as ts

from fetch_stock_history import START_DATE, STOCKS

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

from chatbi_mysql_env import stock_mysql_params

MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE = stock_mysql_params()

SCHEMA_FILE = Path(__file__).resolve().parent / "schema.sql"

INSERT_SQL = """
INSERT INTO stock_daily (
  stock_name, ts_code, trade_date,
  open_price, high_price, low_price, close_price, pre_close,
  price_change, pct_chg, vol, amount
) VALUES (
  %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""


def _parse_sql_statements(sql_text: str) -> list[str]:
    """从 schema 文件中解析可执行的语句（跳过空行、行注释、USE）。"""
    lines: list[str] = []
    for line in sql_text.splitlines():
        if "--" in line:
            line = line[: line.index("--")].rstrip()
        if line.strip():
            lines.append(line)
    text = "\n".join(lines)
    out: list[str] = []
    for chunk in text.split(";"):
        s = chunk.strip()
        if not s:
            continue
        if re.match(r"(?i)^USE\s+", s):
            continue
        out.append(s)
    return out


def _to_trade_date(value: object) -> date:
    """将 tushare 返回的 trade_date（多为 YYYYMMDD 字符串）转为 date。"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, pd.Timestamp):
        return value.date()
    s = str(value).strip()
    if len(s) == 8 and s.isdigit():
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    return pd.to_datetime(s).date()


def ensure_schema(conn_without_db: pymysql.connections.Connection) -> None:
    """执行建库、建表，并切换到 chat_bi_case。"""
    stmts = _parse_sql_statements(SCHEMA_FILE.read_text(encoding="utf-8"))
    if not stmts:
        raise RuntimeError("schema.sql 中未解析到有效 SQL 语句")

    with conn_without_db.cursor() as cur:
        for stmt in stmts:
            cur.execute(stmt)
            if stmt.lstrip().upper().startswith("CREATE DATABASE"):
                conn_without_db.select_db(MYSQL_DATABASE)
    conn_without_db.commit()


def fetch_daily_dataframe() -> pd.DataFrame:
    """与 fetch_stock_history 一致的数据拉取与排序逻辑。"""
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
        raise RuntimeError("未获取到任何行情数据")

    out = pd.concat(frames, ignore_index=True)
    out = out.sort_values(["trade_date", "ts_code"], ascending=True).reset_index(drop=True)
    return out


def dataframe_to_rows(df: pd.DataFrame) -> list[tuple]:
    """DataFrame 转为写入 stock_daily 的行元组列表。"""
    rows: list[tuple] = []
    for _, row in df.iterrows():
        td = _to_trade_date(row["trade_date"])
        rows.append(
            (
                str(row["股票名称"]),
                str(row["ts_code"]),
                td,
                float(row["open"]),
                float(row["high"]),
                float(row["low"]),
                float(row["close"]),
                float(row["pre_close"]),
                float(row["change"]),
                float(row["pct_chg"]),
                int(row["vol"]),
                float(row["amount"]),
            )
        )
    return rows


def main() -> None:
    conn_init = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        charset="utf8mb4",
    )
    try:
        ensure_schema(conn_init)
    finally:
        conn_init.close()

    df = fetch_daily_dataframe()
    rows = dataframe_to_rows(df)

    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DATABASE,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE stock_daily")
            batch = 2000
            for i in range(0, len(rows), batch):
                cur.executemany(INSERT_SQL, rows[i : i + batch])
        conn.commit()
    finally:
        conn.close()

    print(f"已写入 MySQL {MYSQL_DATABASE}.stock_daily，共 {len(rows)} 行")


if __name__ == "__main__":
    main()
