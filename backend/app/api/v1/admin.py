"""管理员后台：/api/v1/admin/vector-dbs。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.core import paths
from app.core.deps import AdminUser
from app.schemas.conversions import admin_resource_to_api
from app.services.admin_stats import list_clone_resource_stats

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/vector-dbs")
def vector_dbs(_admin: AdminUser) -> dict[str, Any]:
    resources = [
        admin_resource_to_api(item)
        for item in list_clone_resource_stats(paths.data_root() / "users")
    ]
    return {
        "vectorDbCount": len(resources),
        "totalVectorDbSizeBytes": sum(int(item["vectorDbSizeBytes"]) for item in resources),
        "totalVoiceModelSizeBytes": sum(int(item["voiceModelSizeBytes"]) for item in resources),
        "resources": resources,
    }
