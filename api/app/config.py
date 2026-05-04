# -*- coding: utf-8 -*-
"""应用配置（环境变量）。"""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Docker 编排下在 compose 中设置 CHATBI_MYSQL_HOST=mysql，优先于宿主机 .env 里的 MYSQL_HOST=127.0.0.1，避免容器内无法解析 mysql
    mysql_host: str = Field(
        default="127.0.0.1",
        validation_alias=AliasChoices("CHATBI_MYSQL_HOST", "MYSQL_HOST"),
    )
    # 容器编排见 compose 默认 3309（避开宿主机常用 3306）；本机直连未设环境变量时与项目默认一致
    mysql_port: int = Field(
        default=3309,
        validation_alias=AliasChoices("CHATBI_MYSQL_PORT", "MYSQL_PORT"),
    )
    mysql_user: str = Field(default="root", validation_alias=AliasChoices("MYSQL_USER"))
    mysql_password: str = Field(
        default="AAAAa@321",
        validation_alias=AliasChoices("MYSQL_PASSWORD"),
    )
    mysql_database: str = Field(
        default="chat_bi_case",
        validation_alias=AliasChoices("MYSQL_DATABASE"),
    )

    redis_url: str = Field(
        default="redis://127.0.0.1:6381/0",
        validation_alias=AliasChoices("REDIS_URL"),
    )

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
