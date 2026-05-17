"""FastAPI 应用工厂：组装 v1 router、CORS、SPA 静态托管。

参考 RCIG 的 backend/app/main.py 风格；保持 /api/v1 版本化前缀。
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.v1 import router as api_v1_router
from app.config import settings
from app.core import paths
from app.core import security as auth

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """启动时 seed 管理员、挂载关闭钩子。"""
    auth.ensure_default_admin(
        settings.default_admin_username,
        settings.default_admin_password,
    )
    logger.info("Cyber Clone Lab backend 启动完成")
    yield
    logger.info("Cyber Clone Lab backend 关闭")


def create_app() -> FastAPI:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = FastAPI(
        title="Cyber Clone Lab",
        description="本地 MVP：上传聊天记录与声音，训练个性化 AI 克隆人。",
        version="0.2.0",
        lifespan=lifespan,
    )

    _configure_cors(app)
    app.include_router(api_v1_router)

    @app.get("/api/health", tags=["系统"])
    def health() -> dict[str, bool]:
        return {"ok": True}

    _mount_frontend(app)

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)

    return app


def _configure_cors(app: FastAPI) -> None:
    if not (settings.enable_dev_cors or os.environ.get("CYBERCLONE_DEV_CORS") == "1"):
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _mount_frontend(app: FastAPI) -> None:
    """生产模式下，把 frontend/dist 挂到根路径并对 SPA 路由 fallback 到 index.html。"""

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return _serve_spa_index()

    @app.get("/{full_path:path}", include_in_schema=False)
    def spa_fallback(full_path: str, _request: Request) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        dist = paths.frontend_dist()
        if full_path:
            candidate = dist / full_path
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if _is_relative_to(resolved, dist.resolve()) and resolved.is_file():
                return FileResponse(resolved)

        return _serve_spa_index()


def _serve_spa_index() -> FileResponse:
    index_path = paths.frontend_dist() / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "前端尚未构建。请在 frontend/ 目录运行 `npm install && npm run build`，"
                "或在开发模式下通过 Vite (`npm run dev`) 访问 http://127.0.0.1:5173。"
            ),
        )
    return FileResponse(index_path)


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


app = create_app()
