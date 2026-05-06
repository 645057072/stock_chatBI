# -*- coding: utf-8 -*-
"""
exc_sql 工具入参校验：仅允许只读查询，降低模型生成恶意 SQL 的风险。

面向过程：校验步骤顺序固定（长度 → 单语句 → 起语句类型 → 危险片段）。
"""

from __future__ import annotations

import re
from typing import Tuple

# 单请求内禁止多条语句（分号后仍存在实质内容）
_MULTI_TAIL = re.compile(r";\s*\S")

# 高风险片段（大小写不敏感）；不包含宽泛的 DROP/DELETE 以免误伤列名/字符串字面量
_DANGER_FRAGMENTS = (
    "into outfile",
    "into dumpfile",
    "load data",
    "load xml",
    "for update",
    "lock tables",
    "unlock tables",
    "procedure analyse",
)


def _strip_leading_sql_comments(s: str) -> str:
    """去掉首部块注释与行注释，便于识别第一条语句关键字。"""
    t = s.lstrip()
    while True:
        if t.startswith("/*"):
            end = t.find("*/")
            if end == -1:
                return ""
            t = t[end + 2 :].lstrip()
            continue
        if t.startswith("--"):
            nl = t.find("\n")
            if nl == -1:
                return ""
            t = t[nl + 1 :].lstrip()
            continue
        if t.startswith("#"):
            nl = t.find("\n")
            if nl == -1:
                return ""
            t = t[nl + 1 :].lstrip()
            continue
        break
    return t


def validate_exc_sql(sql: str) -> Tuple[bool, str]:
    """
    校验 LLM 提交的 SQL 是否可作为只读查询执行。
    返回 (True, "") 或 (False, 中文原因)。
    """
    if sql is None:
        return False, "SQL 不能为空"
    if not isinstance(sql, str):
        return False, "SQL 须为字符串"
    raw = sql.strip()
    if not raw:
        return False, "SQL 不能为空"
    if len(raw) > 200_000:
        return False, "SQL 过长"

    core = raw.rstrip().rstrip(";").strip()
    if not core:
        return False, "SQL 不能为空"
    if ";" in core:
        return False, "禁止在同一请求中执行多条 SQL（检测到分号）"
    if _MULTI_TAIL.search(raw):
        return False, "禁止多条 SQL 语句"

    head = _strip_leading_sql_comments(core)
    if not head:
        return False, "仅允许 SELECT 或 WITH 开头的只读查询"
    if not re.match(r"(SELECT|WITH)\b", head, re.IGNORECASE):
        return False, "仅允许以 SELECT 或 WITH（公用表表达式）开头的只读查询"

    lower = core.lower()
    for frag in _DANGER_FRAGMENTS:
        if frag in lower:
            return False, f"SQL 包含禁止片段（{frag}），仅允许只读查询"

    return True, ""


def validate_exc_sql_or_raise(sql: str) -> None:
    """校验失败时抛出 ValueError，便于调用方统一捕获。"""
    ok, msg = validate_exc_sql(sql)
    if not ok:
        raise ValueError(msg)
