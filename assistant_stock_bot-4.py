# -*- coding: utf-8 -*-
"""
股票查询助手 v4（基于 MySQL 本地库 chat_bi_case.stock_daily）。

在 v2 基础上增加：
- boll_detection：布林带 20 日 + 2σ，检测超买/超卖点（默认近一年；可自定义起止日期）
- 说明：用户若提到 sqlite，本项目行情实际存储在 MySQL；本工具从 MySQL 读取，与全项目数据源一致。

依赖：
- 环境变量 DASHSCOPE_API_KEY（DashScope）
- statsmodels（ARIMA）
- MySQL：.env / 环境变量 CHATBI_MYSQL_*、MYSQL_*（默认端口 3309）
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
from typing import Optional

import dashscope
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from qwen_agent.agents import Assistant
from qwen_agent.tools.base import BaseTool, register_tool
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

load_dotenv()

from chatbi_mysql_env import stock_mysql_params
# 解决中文显示问题
plt.rcParams["font.sans-serif"] = [
    "SimHei",
    "Microsoft YaHei",
    "SimSun",
    "Arial Unicode MS",
]
plt.rcParams["axes.unicode_minus"] = False

# DashScope 配置
dashscope.api_key = os.getenv("DASHSCOPE_API_KEY", "")
dashscope.timeout = 30

# MySQL 连接（与 .env 一致）
MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE = stock_mysql_params()

# 输出图片目录
IMAGE_DIR = os.path.join(os.path.dirname(__file__), "image_show")

# ====== 股票助手 system prompt ======
system_prompt = """你是股票查询助手。你连接的 MySQL 数据库中已经有历史日线行情表（唯一数据源）：

CREATE TABLE stock_daily (
  id BIGINT UNSIGNED AUTO_INCREMENT,
  stock_name VARCHAR(32),   -- 股票名称
  ts_code VARCHAR(16),      -- 证券代码，如 600519.SH
  trade_date DATE,          -- 交易日期
  open_price DECIMAL(16,4), -- 开盘价
  high_price DECIMAL(16,4), -- 最高价
  low_price DECIMAL(16,4),  -- 最低价
  close_price DECIMAL(16,4),-- 收盘价
  pre_close DECIMAL(16,4),  -- 昨收价
  price_change DECIMAL(16,4),-- 涨跌额
  pct_chg DECIMAL(12,4),    -- 涨跌幅(%)
  vol BIGINT UNSIGNED,      -- 成交量(手)
  amount DECIMAL(20,4)      -- 成交额(千元)
);

强规则（必须遵守）：
1) 任何涉及“数量/金额/涨跌幅/均值/排名/是否存在某年数据/最大最小日期”等数据结论，必须先调用 exc_sql 查询数据库，再基于结果回答；禁止在未查询前凭空推断（例如“2025 年没有数据”“数据尚未更新”等）。
2) SQL 只能查询 stock_daily 表（禁止引用其它表/视图/CTE 里不存在的表名），字段必须来自上面的表结构。
3) 若用户问“某年/某月是否有数据”，先用 SQL 查询该股票/范围的 MIN(trade_date)、MAX(trade_date) 或 COUNT(*) 来确认。
4) 输出时：当 exc_sql 返回 markdown 表格/图片时，必须原样输出工具返回的全部内容（包括图片 markdown），不要省略。
5) 写 SQL 时尽量包含 stock_name（若用户 SQL 未选 stock_name，工具会自动补全，但你仍优先在 SQL 里显式选择 stock_name）。
6) 当用户要求“预测未来股价 / ARIMA / 未来 n 天”等时，必须调用 arima_stock 工具：参数 ts_code（必填）、n（预测交易日数量，必填）。不要手写预测数值。
7) 当用户要求“布林带 / 超买超卖 / BOLL”等时，必须调用 boll_detection 工具：ts_code（必填）；start_date、end_date（可选，YYYY-MM-DD，默认近一年至今天）。**工具返回后必须原样粘贴全部内容（含「触点日期列表」行与表格），禁止自行改写、概括或另写一套日期。**

你需要根据用户问题生成 SQL（MySQL 方言）并调用 exc_sql 工具执行，返回查询结果；预测类问题调用 arima_stock；布林带检测调用 boll_detection。

常用查询示例（按需选择）：
- 某只股票某段时间收盘价走势：
  SELECT trade_date, close_price FROM stock_daily WHERE ts_code='600519.SH' AND trade_date BETWEEN '2020-01-01' AND CURDATE() ORDER BY trade_date;
- 多只股票同一时间段对比：
  SELECT trade_date, ts_code, close_price FROM stock_daily WHERE ts_code IN (...) AND trade_date BETWEEN ... ORDER BY trade_date, ts_code;
- 周/月聚合（示例：按月平均收盘价）：
  SELECT DATE_FORMAT(trade_date,'%Y-%m-01') AS month, ts_code, AVG(close_price) AS avg_close
  FROM stock_daily
  WHERE ...
  GROUP BY month, ts_code
  ORDER BY month, ts_code;

重要：每当 exc_sql / arima_stock / boll_detection 工具返回 markdown 表格和图片时，你必须原样输出工具返回的全部内容（包括图片 markdown），不要只总结表格，也不要省略图片。"""

# ====== 工具描述（供 qwen-agent 识别） ======
functions_desc = [
    {
        "name": "exc_sql",
        "description": "执行 SQL 查询（MySQL），返回结果表格并自动可视化",
        "parameters": {
            "type": "object",
            "properties": {
                "sql_input": {
                    "type": "string",
                    "description": "要执行的 SQL 语句（MySQL）",
                }
            },
            "required": ["sql_input"],
        },
    },
    {
        "name": "arima_stock",
        "description": "从本地 MySQL 取该股票截止今天前一年的收盘价，ARIMA(5,1,5) 建模并预测未来 n 个交易日收盘价",
        "parameters": {
            "type": "object",
            "properties": {
                "ts_code": {
                    "type": "string",
                    "description": "证券代码，如 600519.SH（必填）",
                },
                "n": {
                    "type": "integer",
                    "description": "向前预测的交易日天数（必填）",
                },
            },
            "required": ["ts_code", "n"],
        },
    },
    {
        "name": "boll_detection",
        "description": "布林带(20日,2σ)检测超买/超卖：从本地 MySQL 读行情，默认近一年，可传 start_date/end_date",
        "parameters": {
            "type": "object",
            "properties": {
                "ts_code": {
                    "type": "string",
                    "description": "证券代码，如 600519.SH（必填）",
                },
                "start_date": {
                    "type": "string",
                    "description": "检测区间开始日期 YYYY-MM-DD（可选，默认今天往前一年）",
                },
                "end_date": {
                    "type": "string",
                    "description": "检测区间结束日期 YYYY-MM-DD（可选，默认今天）",
                },
            },
            "required": ["ts_code"],
        },
    },
]

# ====== 会话隔离 DataFrame 存储 ======
_last_df_dict: dict[int, pd.DataFrame] = {}
_ts_code_name_cache: dict[str, str] = {}


def get_session_id(kwargs) -> Optional[int]:
    """根据 kwargs 获取当前会话的唯一 session_id（用 messages 的 id）。"""
    messages = kwargs.get("messages")
    if messages is not None:
        return id(messages)
    return None


def ensure_event_loop_for_gradio() -> None:
    """在 Gradio Blocks.queue() 之前绑定主线程事件循环（兼容 Python 3.12+）。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())


def _mysql_engine():
    # 重要：密码包含 @ 等特殊字符时，拼接 URL 会被误解析；用 SQLAlchemy URL 安全构造。
    url = URL.create(
        drivername="mysql+pymysql",
        username=MYSQL_USER,
        password=MYSQL_PASSWORD,
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        database=MYSQL_DATABASE,
        query={"charset": "utf8mb4"},
    )
    return create_engine(url, pool_pre_ping=True, connect_args={"connect_timeout": 10})


def _get_ts_code_name_map(engine) -> dict[str, str]:
    """从 stock_daily 读取 ts_code->stock_name 映射，并做缓存。"""
    global _ts_code_name_cache
    if _ts_code_name_cache:
        return _ts_code_name_cache
    try:
        mdf = pd.read_sql(
            text("SELECT DISTINCT ts_code, stock_name FROM stock_daily"),
            engine,
        )
        m = dict(zip(mdf["ts_code"].astype(str), mdf["stock_name"].astype(str)))
        _ts_code_name_cache = m
        return m
    except Exception:
        # 映射读取失败不影响主流程
        return _ts_code_name_cache


def _safe_filename(prefix: str = "chart") -> str:
    return f"{prefix}_{int(time.time() * 1000)}.png"


def _markdown_image(path_rel: str) -> str:
    return f"![图表]({path_rel})"


def generate_chart_png(df_sql: pd.DataFrame, save_path: str) -> None:
    """根据查询结果自动生成图表：优先画时间序列折线，否则画柱状图。"""
    if df_sql is None or df_sql.empty:
        return

    df = df_sql.copy()
    cols = [str(c) for c in df.columns.tolist()]

    # 尝试识别日期列
    date_col = None
    for c in cols:
        if c.lower() in ("trade_date", "date", "day"):
            date_col = c
            break
    if date_col is None:
        # 第一列可转 datetime 也认为是日期
        c0 = cols[0]
        try:
            pd.to_datetime(df[c0].iloc[0])
            date_col = c0
        except Exception:
            date_col = None

    # 识别分组列（ts_code / stock_name）
    group_col = None
    for c in cols:
        if c.lower() in ("ts_code", "stock_name"):
            group_col = c
            break

    # 识别数值列（优先 close_price）
    num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    prefer = None
    for c in cols:
        if c.lower() in ("close_price", "open_price", "high_price", "low_price", "pct_chg", "amount", "vol"):
            if c in df.columns:
                prefer = c
                break
    y_col = prefer or (num_cols[0] if num_cols else None)

    plt.figure(figsize=(10, 6))

    if date_col is not None and y_col is not None:
        # 时间序列折线图（支持按 ts_code 分组）
        df[date_col] = pd.to_datetime(df[date_col])
        df = df.sort_values(date_col)
        if group_col is not None and group_col in df.columns and df[group_col].nunique() <= 10:
            for g, sub in df.groupby(group_col):
                plt.plot(sub[date_col], sub[y_col], label=str(g))
            plt.legend()
        else:
            plt.plot(df[date_col], df[y_col], label=str(y_col))
            plt.legend()
        plt.xlabel(str(date_col))
        plt.ylabel(str(y_col))
        plt.xticks(rotation=45)
        plt.title("行情走势")
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()
        return

    # 兜底：柱状图（取前 30 行，避免过密）
    df2 = df.head(30)
    x = np.arange(len(df2))
    label_col = cols[0]
    if y_col is None:
        plt.text(0.1, 0.5, "无法识别可绘制的数值列", fontsize=12)
    else:
        plt.bar(x, df2[y_col])
        plt.xticks(x, [str(v) for v in df2[label_col]], rotation=45, ha="right")
        plt.xlabel(str(label_col))
        plt.ylabel(str(y_col))
        plt.title("统计图")
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


@register_tool("exc_sql")
class ExcSQLTool(BaseTool):
    """SQL 查询工具：执行 MySQL SQL 并返回 markdown + 图表。"""

    description = "执行 SQL 查询（MySQL），返回结果并自动可视化"
    parameters = [
        {
            "name": "sql_input",
            "type": "string",
            "description": "要执行的 SQL（MySQL）",
            "required": True,
        }
    ]

    def call(self, params: str, **kwargs) -> str:
        # 解析参数（兼容 JSON 字符串或字典）
        if isinstance(params, str):
            args = json.loads(params)
        else:
            args = params
        sql_input = args["sql_input"]

        session_id = get_session_id(kwargs)
        try:
            engine = _mysql_engine()
            df = pd.read_sql(text(sql_input), engine)
        except Exception as e:
            # 直接把异常信息返回给前端，便于定位（例如：MySQL 未启动、账号无权限、端口被占用、驱动缺失等）
            return f"连接/查询 MySQL 失败：{type(e).__name__}: {e}"

        if session_id is not None:
            _last_df_dict[session_id] = df

        if df is None or df.empty:
            return "查询结果为空。"

        # 若结果缺少 stock_name 但包含 ts_code，则自动补全 stock_name 以便展示更完整信息
        cols_lower = {str(c).lower(): c for c in df.columns.tolist()}
        if "stock_name" not in cols_lower and "ts_code" in cols_lower:
            ts_col = cols_lower["ts_code"]
            name_map = _get_ts_code_name_map(engine)
            if name_map:
                df = df.copy()
                df.insert(
                    loc=df.columns.get_loc(ts_col),
                    column="stock_name",
                    value=df[ts_col].astype(str).map(name_map),
                )

        # 只有 1 行结果时：不做可视化、不输出图片（避免误导性的“趋势/统计”图）
        if len(df.index) <= 1:
            return df.head(1).to_markdown(index=False)

        # 展示：前 5 行 + 后 5 行（中间省略），让结果更全面
        head_n = 5
        tail_n = 5
        if len(df.index) <= head_n + tail_n:
            preview_df = df
            preview_md = "### 查询结果\n\n" + preview_df.to_markdown(index=False, tablefmt="github") + "\n"
        else:
            preview_head = df.head(head_n)
            preview_tail = df.tail(tail_n)
            preview_md = (
                "### 查询结果（前 5 行）\n\n"
                + preview_head.to_markdown(index=False, tablefmt="github")
                + "\n\n（中间省略）\n\n"
                + "### 查询结果（后 5 行）\n\n"
                + preview_tail.to_markdown(index=False, tablefmt="github")
                + "\n"
            )

        # 描述统计：优先数值列，便于快速了解分布与极值
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        if numeric_cols:
            desc_df = df[numeric_cols].describe().round(6)
            desc_md = desc_df.to_markdown(tablefmt="github")
        else:
            desc_md = "无可用于描述统计的数值列。"

        os.makedirs(IMAGE_DIR, exist_ok=True)
        filename = _safe_filename("stock")
        save_path = os.path.join(IMAGE_DIR, filename)
        generate_chart_png(df, save_path)

        img_path = os.path.join("image_show", filename)
        img_md = _markdown_image(img_path)
        return f"{preview_md}\n\n### 描述统计\n\n{desc_md}\n\n{img_md}"


# ARIMA 阶数 (p,d,q)，按需求固定为 (5,1,5)
ARIMA_ORDER = (5, 1, 5)
# 训练序列最短有效长度（阶数较高，样本过少易拟合失败）
ARIMA_MIN_SAMPLES = 60
ARIMA_MAX_FORECAST = 60


def _load_stock_history_one_year(engine, ts_code: str) -> pd.DataFrame:
    """从 MySQL 读取某只股票：截止今天、向前一年的日线收盘价。"""
    stmt = text(
        """
        SELECT trade_date, stock_name, close_price
        FROM stock_daily
        WHERE ts_code = :ts_code
          AND trade_date >= DATE_SUB(CURDATE(), INTERVAL 1 YEAR)
          AND trade_date <= CURDATE()
        ORDER BY trade_date
        """
    )
    return pd.read_sql(stmt, engine, params={"ts_code": ts_code})


def _plot_arima_forecast(
    hist_df: pd.DataFrame,
    future_dates: list[pd.Timestamp],
    forecast: np.ndarray,
    ts_code: str,
    stock_name: str,
    save_path: str,
    hist_tail: int = 120,
) -> None:
    """绘制最近一段历史收盘价与预测曲线。"""
    df = hist_df.sort_values("trade_date").tail(min(hist_tail, len(hist_df))).copy()
    df["trade_date"] = pd.to_datetime(df["trade_date"])
    last_td = pd.to_datetime(hist_df["trade_date"].max())

    plt.figure(figsize=(10, 6))
    plt.plot(df["trade_date"], df["close_price"].astype(float), label="历史收盘价")
    plt.plot(future_dates, forecast, "r--", label="ARIMA 预测")
    plt.axvline(x=last_td, color="gray", linestyle=":", alpha=0.85)
    plt.xlabel("日期")
    plt.ylabel("收盘价")
    plt.title(f"{stock_name} ({ts_code}) ARIMA{ARIMA_ORDER}")
    plt.legend()
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


@register_tool("arima_stock")
class ArimaStockTool(BaseTool):
    """
    从本地 MySQL 拉取截止今天前一年的收盘价序列，使用 statsmodels ARIMA(5,1,5) 拟合并预测未来 n 个交易日。
    """

    description = (
        "从本地 MySQL 读取指定 ts_code 截止今天前一年的日线收盘价，使用 ARIMA(5,1,5) 建模，"
        "预测未来 n 个交易日的收盘价，并返回表格与走势图"
    )
    parameters = [
        {
            "name": "ts_code",
            "type": "string",
            "description": "证券代码，如 600519.SH",
            "required": True,
        },
        {
            "name": "n",
            "type": "integer",
            "description": "向前预测的交易日数量",
            "required": True,
        },
    ]

    def call(self, params: str, **kwargs) -> str:
        if isinstance(params, str):
            args = json.loads(params)
        else:
            args = params

        ts_code = str(args.get("ts_code", "")).strip()
        n_raw = args.get("n")
        if not ts_code:
            return "参数 ts_code 为必填。"
        if n_raw is None:
            return "参数 n（预测交易日数）为必填。"
        n = int(n_raw)
        if n <= 0:
            return "n 必须为正整数。"
        if n > ARIMA_MAX_FORECAST:
            return f"n 请不要超过 {ARIMA_MAX_FORECAST}。"

        try:
            from statsmodels.tsa.arima.model import ARIMA
        except ImportError as e:
            return f"未安装 statsmodels，无法使用 ARIMA：{e}。请执行：pip install statsmodels"

        try:
            engine = _mysql_engine()
            df = _load_stock_history_one_year(engine, ts_code)
        except Exception as e:
            return f"读取 MySQL 失败：{type(e).__name__}: {e}"

        if df is None or df.empty:
            return f"未找到 ts_code={ts_code} 在最近一年内（截止今天）的数据。"

        df = df.sort_values("trade_date").dropna(subset=["close_price"])
        y = df["close_price"].astype(float).values
        if len(y) < ARIMA_MIN_SAMPLES:
            return (
                f"历史有效样本不足（当前 {len(y)} 条），ARIMA{ARIMA_ORDER} 建议至少 {ARIMA_MIN_SAMPLES} 条日线，"
                "请补全数据或更换股票。"
            )

        stock_name = str(df["stock_name"].iloc[-1])
        last_td = pd.to_datetime(df["trade_date"].max())

        try:
            model = ARIMA(y, order=ARIMA_ORDER)
            fitted = model.fit()
            fc = fitted.forecast(steps=n)
        except Exception as e:
            return f"ARIMA 拟合或预测失败：{type(e).__name__}: {e}"

        fc_arr = np.asarray(fc, dtype=float).ravel()
        if fc_arr.size < n:
            return f"预测结果长度异常（得到 {fc_arr.size}，期望 {n}）。"

        from pandas.tseries.offsets import BDay

        future_dates = [last_td + BDay(i) for i in range(1, n + 1)]

        out_df = pd.DataFrame(
            {
                "predict_date": [d.date() for d in future_dates],
                "predict_close_price": fc_arr[:n],
            }
        )

        meta = (
            "### ARIMA 预测说明\n\n"
            f"- **ts_code**: {ts_code}\n"
            f"- **stock_name**: {stock_name}\n"
            f"- **模型**: ARIMA{ARIMA_ORDER}（statsmodels）\n"
            f"- **训练数据**: 截止 {last_td.date()}，取 MySQL 中「今天往前一年」的日线收盘价\n"
            f"- **预测**: 未来 **{n}** 个交易日收盘价\n\n"
            "> 提示：预测仅供技术演示，不构成投资建议。\n\n"
        )
        table_md = "### 预测结果\n\n" + out_df.to_markdown(index=False, tablefmt="github") + "\n"

        os.makedirs(IMAGE_DIR, exist_ok=True)
        filename = _safe_filename("arima")
        save_path = os.path.join(IMAGE_DIR, filename)
        _plot_arima_forecast(df, future_dates, fc_arr[:n], ts_code, stock_name, save_path)
        img_md = _markdown_image(os.path.join("image_show", filename))

        return f"{meta}{table_md}\n{img_md}"


# 布林带参数：20 日均线 ± 2 倍标准差
BOLL_PERIOD = 20
BOLL_STD_MULT = 2.0
# 为滚动窗口预留的历史长度（日历天，略大于 20 个交易日）
BOLL_WARMUP_DAYS = 60


def _resolve_boll_user_window(
    start_raw: Optional[str],
    end_raw: Optional[str],
) -> tuple[pd.Timestamp, pd.Timestamp]:
    """解析用户自定义检测区间（不含默认近一年逻辑；默认逻辑走 MySQL 对齐）。"""
    from datetime import date

    today = pd.Timestamp(date.today())
    if start_raw and end_raw:
        win_start = pd.to_datetime(start_raw).normalize()
        win_end = pd.to_datetime(end_raw).normalize()
    elif start_raw:
        win_start = pd.to_datetime(start_raw).normalize()
        win_end = today
    else:
        win_end = pd.to_datetime(end_raw).normalize()
        win_start = win_end - pd.DateOffset(years=1)
    if win_end < win_start:
        win_start, win_end = win_end, win_start
    return win_start, win_end


def _get_boll_default_window_mysql(engine, ts_code: str) -> tuple[pd.Timestamp, pd.Timestamp]:
    """默认「近一年」：以该股票最新交易日为锚点，向前回溯约 1 年交易日（252 个交易日）。"""
    lookback_trading_days = 252
    q = text(
        """
        SELECT trade_date
        FROM stock_daily
        WHERE ts_code = :ts_code
        ORDER BY trade_date DESC
        LIMIT :n
        """
    )
    df = pd.read_sql(q, engine, params={"ts_code": ts_code, "n": lookback_trading_days})
    if df.empty:
        raise ValueError("无法解析默认检测区间（可能无该 ts_code 数据）")
    d = pd.to_datetime(df["trade_date"]).sort_values()
    ws = d.iloc[0].normalize()
    we = d.iloc[-1].normalize()
    return ws, we


def _clip_boll_window_to_market(engine, ts_code: str, win_start: pd.Timestamp, win_end: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    """结束日不超过 min(CURDATE(), 库中该票最新交易日)；开始日若晚于结束日则收紧。"""
    q = text(
        """
        SELECT
          LEAST(CURDATE(), COALESCE(MAX(trade_date), CURDATE())) AS cap
        FROM stock_daily
        WHERE ts_code = :ts_code
        """
    )
    cap_df = pd.read_sql(q, engine, params={"ts_code": ts_code})
    if cap_df.empty or cap_df["cap"].iloc[0] is None:
        return win_start, win_end
    cap = pd.to_datetime(cap_df["cap"].iloc[0]).normalize()
    we = min(win_end, cap)
    ws = win_start
    if we < ws:
        ws = we
    return ws, we


def _load_stock_range_for_boll(
    engine,
    ts_code: str,
    fetch_start,
    fetch_end,
) -> pd.DataFrame:
    """按日期区间从 MySQL 读取日线（含 stock_name、收盘价）。"""
    stmt = text(
        """
        SELECT trade_date, stock_name, close_price
        FROM stock_daily
        WHERE ts_code = :ts_code
          AND trade_date >= :fetch_start
          AND trade_date <= :fetch_end
        ORDER BY trade_date
        """
    )
    return pd.read_sql(
        stmt,
        engine,
        params={
            "ts_code": ts_code,
            "fetch_start": fetch_start,
            "fetch_end": fetch_end,
        },
    )


def _plot_boll_chart(
    df_vis: pd.DataFrame,
    hits: pd.DataFrame,
    ts_code: str,
    stock_name: str,
    save_path: str,
) -> None:
    """绘制检测区间内收盘价与布林带，并标出超买/超卖点。"""
    plt.figure(figsize=(11, 6))
    plt.plot(df_vis["trade_date"], df_vis["close_price"].astype(float), label="收盘价", color="black", linewidth=1)
    plt.plot(df_vis["trade_date"], df_vis["boll_mid"], label=f"中轨({BOLL_PERIOD}日)", color="blue", linewidth=1)
    plt.plot(df_vis["trade_date"], df_vis["boll_upper"], label=f"上轨(+{BOLL_STD_MULT}σ)", color="red", linestyle="--", linewidth=0.9)
    plt.plot(df_vis["trade_date"], df_vis["boll_lower"], label=f"下轨(-{BOLL_STD_MULT}σ)", color="green", linestyle="--", linewidth=0.9)
    if not hits.empty:
        ob = hits[hits["boll_signal"] == "超买"]
        os_ = hits[hits["boll_signal"] == "超卖"]
        if not ob.empty:
            plt.scatter(ob["trade_date"], ob["close_price"].astype(float), color="red", s=36, zorder=5, label="超买")
        if not os_.empty:
            plt.scatter(os_["trade_date"], os_["close_price"].astype(float), color="green", s=36, zorder=5, label="超卖")
    plt.xlabel("日期")
    plt.ylabel("价格")
    plt.title(f"{stock_name} ({ts_code}) 布林带 {BOLL_PERIOD}日±{BOLL_STD_MULT}σ")
    plt.legend(loc="best", fontsize=8)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(save_path)
    plt.close()


@register_tool("boll_detection")
class BollDetectionTool(BaseTool):
    """
    从本地 MySQL 读取指定股票的日线收盘价，计算 20 日布林带与 2σ 上下轨，
    在指定时间范围内标记收盘价突破上轨（超买）或跌破下轨（超卖）的交易日。
    """

    description = (
        "布林带检测：20 日均线为中轨，±2σ 为上下轨；从 MySQL 读行情，默认检测近一年超买/超卖日，"
        "可通过 start_date、end_date（YYYY-MM-DD）自定义区间"
    )
    parameters = [
        {
            "name": "ts_code",
            "type": "string",
            "description": "证券代码，如 600519.SH",
            "required": True,
        },
        {
            "name": "start_date",
            "type": "string",
            "description": "检测区间开始 YYYY-MM-DD（可选）",
            "required": False,
        },
        {
            "name": "end_date",
            "type": "string",
            "description": "检测区间结束 YYYY-MM-DD（可选）",
            "required": False,
        },
    ]

    def call(self, params: str, **kwargs) -> str:
        if isinstance(params, str):
            args = json.loads(params)
        else:
            args = params

        ts_code = str(args.get("ts_code", "")).strip()
        start_raw = args.get("start_date")
        end_raw = args.get("end_date")
        if isinstance(start_raw, str) and not start_raw.strip():
            start_raw = None
        if isinstance(end_raw, str) and not end_raw.strip():
            end_raw = None

        if not ts_code:
            return "参数 ts_code 为必填。"

        try:
            engine = _mysql_engine()
            if not start_raw and not end_raw:
                win_start, win_end = _get_boll_default_window_mysql(engine, ts_code)
            else:
                win_start, win_end = _resolve_boll_user_window(
                    str(start_raw) if start_raw is not None else None,
                    str(end_raw) if end_raw is not None else None,
                )
                win_start, win_end = _clip_boll_window_to_market(engine, ts_code, win_start, win_end)
        except Exception as e:
            return f"解析检测区间失败：{type(e).__name__}: {e}"

        fetch_start = (win_start - pd.Timedelta(days=BOLL_WARMUP_DAYS)).date()
        fetch_end = win_end.date()

        try:
            df = _load_stock_range_for_boll(engine, ts_code, fetch_start, fetch_end)
        except Exception as e:
            return f"读取 MySQL 失败：{type(e).__name__}: {e}"

        if df is None or df.empty:
            return f"未找到 ts_code={ts_code} 在 {fetch_start} ~ {fetch_end} 范围内的数据。"

        df = df.sort_values("trade_date").reset_index(drop=True)
        df["trade_date"] = pd.to_datetime(df["trade_date"])
        close = df["close_price"].astype(float)

        df["boll_mid"] = close.rolling(BOLL_PERIOD, min_periods=BOLL_PERIOD).mean()
        std20 = close.rolling(BOLL_PERIOD, min_periods=BOLL_PERIOD).std(ddof=0)
        df["boll_upper"] = df["boll_mid"] + BOLL_STD_MULT * std20
        df["boll_lower"] = df["boll_mid"] - BOLL_STD_MULT * std20

        sig = np.where(close > df["boll_upper"], "超买", np.where(close < df["boll_lower"], "超卖", ""))
        df["boll_signal"] = sig

        win_mask = (df["trade_date"] >= win_start) & (df["trade_date"] <= win_end)
        hits = df.loc[win_mask & (df["boll_signal"] != "")].copy()

        stock_name = str(df["stock_name"].iloc[-1])

        meta = (
            "### 布林带检测说明\n\n"
            f"- **ts_code**: {ts_code}\n"
            f"- **stock_name**: {stock_name}\n"
            f"- **规则**: {BOLL_PERIOD} 日移动平均为中轨，上下轨 = 中轨 ± {BOLL_STD_MULT}×{BOLL_PERIOD}日收盘价标准差（σ 为同窗口收盘价总体标准差，ddof=0）\n"
            f"- **检测区间**: {win_start.date()} ~ {win_end.date()}（默认模式按 **该股票最新交易日向前约252个交易日** 回推；数据来源：`stock_daily`）\n"
            f"- **超买**: 收盘价 > 上轨；**超卖**: 收盘价 < 下轨\n"
            f"- **区间内触点数量**: 超买 {int((hits['boll_signal'] == '超买').sum())} 日，"
            f"超卖 {int((hits['boll_signal'] == '超卖').sum())} 日\n"
            f"- **重要**: 下列「触点日期列表」与表格为唯一权威结果，答复时请完整复制，勿改写日期。\n\n"
        )

        if hits.empty:
            table_md = "### 触点列表\n\n区间内无超买/超卖触点（收盘价未突破上下轨）。\n\n"
            list_md = "### 触点日期列表\n\n- 超买: （无）\n- 超卖: （无）\n\n"
        else:
            show_cols = [
                "trade_date",
                "stock_name",
                "close_price",
                "boll_mid",
                "boll_upper",
                "boll_lower",
                "boll_signal",
            ]
            disp = hits[show_cols].copy()
            disp["trade_date"] = disp["trade_date"].dt.date
            for c in ["close_price", "boll_mid", "boll_upper", "boll_lower"]:
                disp[c] = disp[c].astype(float).round(4)
            table_md = "### 触点列表\n\n" + disp.to_markdown(index=False, tablefmt="github") + "\n\n"
            ob_dates = sorted(
                hits.loc[hits["boll_signal"] == "超买", "trade_date"].dt.strftime("%Y-%m-%d").unique().tolist()
            )
            os_dates = sorted(
                hits.loc[hits["boll_signal"] == "超卖", "trade_date"].dt.strftime("%Y-%m-%d").unique().tolist()
            )
            list_md = (
                "### 触点日期列表（程序生成，与上表一致）\n\n"
                f"- **超买**: {', '.join(ob_dates)}\n"
                f"- **超卖**: {', '.join(os_dates)}\n\n"
            )

        df_vis = df.loc[win_mask].dropna(subset=["boll_mid"])
        if df_vis.empty:
            return meta + table_md + f"区间内有效布林带数据不足（需至少 {BOLL_PERIOD} 个交易日历史，请扩大查询范围或向前多取数据）。"

        os.makedirs(IMAGE_DIR, exist_ok=True)
        filename = _safe_filename("boll")
        save_path = os.path.join(IMAGE_DIR, filename)
        _plot_boll_chart(df_vis, hits, ts_code, stock_name, save_path)
        img_md = _markdown_image(os.path.join("image_show", filename))

        return f"{meta}{list_md}{table_md}{img_md}"


def init_agent_service():
    """初始化股票助手服务。"""
    llm_cfg = {
        "model": "qwen-turbo",
        "timeout": 30,
        "retry_count": 3,
    }

    function_list: list = ["exc_sql", "arima_stock", "boll_detection"]
    # 默认关闭 Tavily MCP，避免 WebUI 在插件参数绑定时出现 endpoint 参数不匹配错误。
    # 如需启用，请同时设置：
    #   TAVILY_API_KEY=...
    #   ENABLE_TAVILY_MCP=1
    tavily_key = os.getenv("TAVILY_API_KEY")
    enable_tavily_mcp = os.getenv("ENABLE_TAVILY_MCP", "0") == "1"
    if tavily_key and enable_tavily_mcp:
        function_list.append(
            {
                "mcpServers": {
                    "tavily-mcp": {
                        "args": ["-y", "tavily-mcp@0.1.4"],
                        "autoApprove": [],
                        "command": "npx",
                        "env": {"TAVILY_API_KEY": tavily_key},
                    }
                }
            }
        )

    bot = Assistant(
        llm=llm_cfg,
        name="股票查询助手（ARIMA+布林带）",
        description="基于 MySQL 的历史行情查询、可视化、ARIMA 预测与布林带超买超卖检测",
        system_message=system_prompt,
        function_list=function_list,
        # 仅用于补充“如何写 SQL”的偏好，不用于提供任何真实数据
        files=["faq.txt"],
    )
    print("助手初始化成功！")
    return bot


def app_tui():
    """终端交互模式。"""
    try:
        bot = init_agent_service()
        messages = []
        while True:
            try:
                query = input("user question: ").strip()
                if not query:
                    print("user question cannot be empty！")
                    continue
                messages.append({"role": "user", "content": query})
                response = []
                for response in bot.run(messages):
                    print("bot response:", response)
                messages.extend(response)
            except KeyboardInterrupt:
                print("\n已退出。")
                break
            except Exception as e:
                print(f"处理请求时出错: {str(e)}")
    except Exception as e:
        print(f"启动终端模式失败: {str(e)}")


def app_gui():
    """Web 图形界面模式。"""
    ensure_event_loop_for_gradio()
    from qwen_agent.gui import WebUI

    try:
        print("正在启动 Web 界面...")
        bot = init_agent_service()
        chatbot_config = {
            "prompt.suggestions": [
                "查询2025年全年贵州茅台的收盘价走势",
                "统计2025年3月广发证券的日均成交量",
                "用 ARIMA 预测贵州茅台未来10个交易日的收盘价",
                "检测贵州茅台近一年布林带20日2σ的超买和超卖日期",
            ]
        }
        print("Web 界面准备就绪，正在启动服务...")
        WebUI(bot, chatbot_config=chatbot_config).run()
    except Exception as e:
        print(f"启动 Web 界面失败: {str(e)}")
        print("请检查本机端口/代理设置，以及 DASHSCOPE_API_KEY。")


if __name__ == "__main__":
    # 默认尝试 Web；缺少依赖或启动失败时回退终端
    try:
        app_gui()
    except ImportError:
        print("未安装 Web 界面依赖（需要 gradio 与 modelscope_studio）。")
        print('可执行: pip install "gradio==5.23.1" "gradio-client==1.8.0" "modelscope-studio==1.1.7"')
        print("当前已切换为终端交互模式。\n")
        app_tui()

