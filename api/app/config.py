# -*- coding: utf-8 -*-
"""应用配置（环境变量）。"""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_user: str = "root"
    mysql_password: str = "AAAAa@321"
    mysql_database: str = "chat_bi_case"

    redis_url: str = "redis://127.0.0.1:6379/0"

    # 会话 Cookie
    session_cookie_name: str = "chatbi_session"
    session_ttl_seconds: int = 7 * 24 * 3600

    # 限流：每分钟每用户聊天次数
    rate_limit_chat_per_minute: int = 60
    # 限流：每分钟每 IP 登录/注册次数
    rate_limit_auth_per_minute: int = 20

    # 单用户 Redis 中保留的最大对话消息条数（role/content 列表总长度上限）
    chat_history_max_messages: int = 40

    # 静态资源 URL 前缀（经 Nginx /api/ 反代后，图片 markdown 使用此前缀）
    public_static_prefix: str = "/api/static"

    # 仅 HTTPS 部署时设为 true（本地直连 HTTP 调试时用 false）
    cookie_secure: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
