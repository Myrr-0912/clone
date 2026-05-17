"""可在测试中 monkeypatch 的路径常量。

旧代码用 module 级 `web_module.DATA_ROOT = ...` 重写来切换数据目录；
FastAPI router 通过 `paths.data_root()` 读取，让测试只需替换这里的一个值。
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]

DATA_ROOT: Path = PROJECT_ROOT / "data"
FRONTEND_DIST: Path = PROJECT_ROOT / "frontend" / "dist"
ENV_PATH: Path = PROJECT_ROOT / ".env"
SESSION_COOKIE_NAME: str = "cyberclone_session"


def data_root() -> Path:
    return DATA_ROOT


def frontend_dist() -> Path:
    return FRONTEND_DIST


def env_path() -> Path:
    return ENV_PATH
