"""应用配置：通过 pydantic-settings 从环境变量 / `.env` 读取。

参考 RCIG 风格保持单例 `settings`。本项目仍以独立 ``cyberclone.env`` 配置
语音 / LLM 后端为主，这里只暴露 HTTP 层与跨域所需的开关。
"""

from __future__ import annotations

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict

_ROOT_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    # 应用基础配置
    app_env: str = "development"
    log_level: str = "INFO"

    # 跨域：开发期 Vite dev server 默认在 5173
    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    enable_dev_cors: bool = False

    # 默认管理员（开发模式自动 seed）
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"

    model_config = SettingsConfigDict(
        env_file=str(_ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        env_prefix="CYBERCLONE_",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()
