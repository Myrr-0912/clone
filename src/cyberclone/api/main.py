"""FastAPI 应用工厂：组装 router、CORS、SPA 静态托管。"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from .. import auth
from . import paths
from .routers import admin, auth as auth_router, chat, clones, voice


def create_app() -> FastAPI:
    auth.ensure_default_admin()
    app = FastAPI(title="Cyber Clone MVP", version="0.2.0")

    _configure_cors(app)

    app.include_router(auth_router.router)
    app.include_router(clones.router)
    app.include_router(voice.router)
    app.include_router(chat.router)
    app.include_router(admin.router)

    @app.get("/api/health")
    def health() -> dict[str, bool]:
        return {"ok": True}

    _mount_frontend(app)

    return app


def _configure_cors(app: FastAPI) -> None:
    if os.environ.get("CYBERCLONE_DEV_CORS") != "1":
        return
    origins_env = os.environ.get("CYBERCLONE_DEV_ORIGINS") or "http://127.0.0.1:5173,http://localhost:5173"
    origins = [origin.strip() for origin in origins_env.split(",") if origin.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
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
    def spa_fallback(full_path: str, request: Request) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")

        dist = paths.frontend_dist()
        # 命中具体静态资源（assets/main.js、favicon 等）
        if full_path:
            candidate = dist / full_path
            try:
                resolved = candidate.resolve()
            except OSError:
                resolved = candidate
            if _is_relative_to(resolved, dist.resolve()) and resolved.is_file():
                return FileResponse(resolved)

        # 其余 GET 视为 SPA 路由，全部回退到 index.html
        return _serve_spa_index()

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse({"error": exc.detail}, status_code=exc.status_code)


def _serve_spa_index() -> FileResponse:
    index_path = paths.frontend_dist() / "index.html"
    if not index_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "前端尚未构建。请在 frontend/ 目录运行 `pnpm install && pnpm build`，"
                "或在开发模式下通过 Vite (`pnpm dev`) 访问 http://127.0.0.1:5173。"
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
