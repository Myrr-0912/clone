"""API v1 路由统一注册（参考 RCIG 风格）。"""

from fastapi import APIRouter

from .admin import router as admin_router
from .auth import router as auth_router
from .chat import router as chat_router
from .clones import router as clones_router
from .voice import router as voice_router

router = APIRouter(prefix="/api/v1")
router.include_router(auth_router)
router.include_router(clones_router)
router.include_router(voice_router)
router.include_router(chat_router)
router.include_router(admin_router)
