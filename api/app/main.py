# -*- coding: utf-8 -*-
"""FastAPI：注册/登录、会话（Redis）、限流、股票助手对话。"""

from __future__ import annotations

import json
import re
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool

from app.auth_util import hash_password, verify_password
from app.config import get_settings
from app.db import get_engine
from app.db_schema import APP_USERS_CREATE_SQL
from app.rate_limit import allow
from app.redis_util import get_redis
from app.paths import image_show_dir
from app.stock_bridge import rewrite_markdown_images, run_agent_turn


@asynccontextmanager
async def lifespan(app: FastAPI):
    import logging
    import os
    import time

    os.makedirs(image_show_dir(), exist_ok=True)
    log = logging.getLogger("uvicorn.error")
    s = get_settings()
    # depends_on healthy 后嵌入 DNS 仍可能稍晚就绪，短暂重试避免 api 直接退出
    last_exc: Exception | None = None
    for attempt in range(45):
        try:
            with get_engine().begin() as conn:
                conn.execute(text("SELECT 1"))
                tbl = conn.execute(
                    text(
                        "SELECT COUNT(*) FROM information_schema.tables "
                        "WHERE table_schema = :db AND table_name = 'app_users'"
                    ),
                    {"db": s.mysql_database},
                ).scalar_one()
                if tbl == 0:
                    log.warning(
                        "未检测到 app_users 表，执行 CREATE TABLE IF NOT EXISTS（与 deploy/init-app.sql 一致）"
                    )
                    conn.execute(text(APP_USERS_CREATE_SQL))
            break
        except Exception as exc:
            last_exc = exc
            log.warning(
                "MySQL 启动校验第 %s 次失败（host=%s port=%s），2s 后重试：%s",
                attempt + 1,
                s.mysql_host,
                s.mysql_port,
                exc,
            )
            time.sleep(2)
    else:
        log.error(
            "MySQL 启动校验最终失败：host=%s port=%s database=%s user=%s，错误=%s",
            s.mysql_host,
            s.mysql_port,
            s.mysql_database,
            s.mysql_user,
            last_exc,
        )
        assert last_exc is not None
        raise last_exc
    yield


app = FastAPI(title="ChatBI Stock API", lifespan=lifespan)

# 助手生成的图表静态目录（URL 由 Nginx 将 /api 前缀转到本服务）
app.mount(
    "/static",
    StaticFiles(directory=image_show_dir()),
    name="static",
)


class RegisterBody(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_bytes(cls, v: str) -> str:
        # bcrypt 仅支持最多 72 字节；超长会在哈希阶段抛错导致 500
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长（UTF-8 不可超过 72 字节），请缩短或使用更少字符")
        return v


class LoginBody(BaseModel):
    username: str = Field(..., min_length=1, max_length=32)
    password: str = Field(..., min_length=1, max_length=128)

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_bytes_login(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长（UTF-8 不可超过 72 字节）")
        return v


class ChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)


_username_re = re.compile(r"^[a-zA-Z0-9_\u4e00-\u9fff]+$")


def _validate_username(username: str) -> None:
    if not _username_re.match(username):
        raise HTTPException(
            status_code=400,
            detail="用户名仅允许字母、数字、下划线或中文",
        )


def _client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


def extract_assistant_text(delta: list[Any]) -> str:
    """从助手增量消息中提取 assistant 文本内容。"""
    chunks: list[str] = []
    for item in delta:
        if not isinstance(item, dict):
            continue
        if item.get("role") != "assistant":
            continue
        c = item.get("content")
        if isinstance(c, str):
            chunks.append(c)
        elif c is not None:
            chunks.append(str(c))
    return "\n\n".join(chunks) if chunks else "（无文本回复）"


def _chat_history_key(user_id: int) -> str:
    return f"chat:hist:{user_id}"


def _load_messages(r, user_id: int) -> list:
    raw = r.get(_chat_history_key(user_id))
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except json.JSONDecodeError:
        pass
    return []


def _save_messages(r, user_id: int, messages: list) -> None:
    s = get_settings()
    max_len = s.chat_history_max_messages
    if len(messages) > max_len:
        messages = messages[-max_len:]
    r.set(_chat_history_key(user_id), json.dumps(messages, ensure_ascii=False))


SessionUser = dict[str, Any]


async def get_session_user(request: Request) -> SessionUser:
    settings = get_settings()
    sid = request.cookies.get(settings.session_cookie_name)
    if not sid:
        raise HTTPException(status_code=401, detail="未登录")
    r = get_redis()
    raw = r.get(f"sess:{sid}")
    if not raw:
        raise HTTPException(status_code=401, detail="会话已失效")
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "user_id" in data:
            return data
    except json.JSONDecodeError:
        pass
    raise HTTPException(status_code=401, detail="会话无效")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/register")
def register(request: Request, body: RegisterBody):
    settings = get_settings()
    r = get_redis()
    ip = _client_ip(request)
    if not allow(r, f"rl:auth:{ip}", settings.rate_limit_auth_per_minute):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    _validate_username(body.username)

    eng = get_engine()
    with eng.begin() as conn:
        row = conn.execute(
            text("SELECT id FROM app_users WHERE username = :u"),
            {"u": body.username},
        ).first()
        if row:
            raise HTTPException(status_code=409, detail="用户名已存在")
        conn.execute(
            text(
                "INSERT INTO app_users (username, password_hash) VALUES (:u, :p)"
            ),
            {"u": body.username, "p": hash_password(body.password)},
        )
    return {"ok": True}


@app.post("/auth/login")
def login(request: Request, response: Response, body: LoginBody):
    settings = get_settings()
    r = get_redis()
    ip = _client_ip(request)
    if not allow(r, f"rl:auth:{ip}", settings.rate_limit_auth_per_minute):
        raise HTTPException(status_code=429, detail="请求过于频繁，请稍后再试")

    eng = get_engine()
    with eng.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, username, password_hash FROM app_users WHERE username = :u"
            ),
            {"u": body.username},
        ).mappings().first()
    if not row or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    sid = uuid.uuid4().hex
    payload = json.dumps(
        {"user_id": row["id"], "username": row["username"]},
        ensure_ascii=False,
    )
    r.setex(f"sess:{sid}", settings.session_ttl_seconds, payload)

    response.set_cookie(
        key=settings.session_cookie_name,
        value=sid,
        max_age=settings.session_ttl_seconds,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return {"ok": True, "username": row["username"]}


@app.post("/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: Annotated[SessionUser, Depends(get_session_user)],
):
    settings = get_settings()
    sid = request.cookies.get(settings.session_cookie_name)
    if sid:
        get_redis().delete(f"sess:{sid}")
    response.delete_cookie(settings.session_cookie_name, path="/")
    return {"ok": True}


@app.get("/auth/me")
def me(user: Annotated[SessionUser, Depends(get_session_user)]):
    return {"user_id": user["user_id"], "username": user["username"]}


@app.post("/chat")
async def chat(
    request: Request,
    body: ChatBody,
    user: Annotated[SessionUser, Depends(get_session_user)],
):
    settings = get_settings()
    r = get_redis()
    uid = int(user["user_id"])
    if not allow(r, f"rl:chat:{uid}", settings.rate_limit_chat_per_minute):
        raise HTTPException(status_code=429, detail="对话请求过于频繁")

    messages = _load_messages(r, uid)
    messages.append({"role": "user", "content": body.message.strip()})

    try:
        delta = await run_in_threadpool(run_agent_turn, messages)
    except Exception as e:
        messages.pop()
        raise HTTPException(status_code=500, detail=f"助手处理失败: {e!s}") from e

    messages.extend(delta)
    _save_messages(r, uid, messages)

    reply = extract_assistant_text(delta)
    reply = rewrite_markdown_images(reply, settings.public_static_prefix)
    return {"reply": reply}


@app.post("/chat/clear")
def clear_history(user: Annotated[SessionUser, Depends(get_session_user)]):
    r = get_redis()
    r.delete(_chat_history_key(int(user["user_id"])))
    return {"ok": True}


@app.get("/chat/history")
def chat_history(user: Annotated[SessionUser, Depends(get_session_user)]):
    """供前端刷新后恢复 Redis 中保存的多轮对话（原始消息结构）。"""
    r = get_redis()
    return {"messages": _load_messages(r, int(user["user_id"]))}
