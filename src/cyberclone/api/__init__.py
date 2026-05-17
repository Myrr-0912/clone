"""FastAPI 适配层，将 cyberclone 领域模块包装成 JSON API。"""

from .main import create_app

__all__ = ["create_app"]
