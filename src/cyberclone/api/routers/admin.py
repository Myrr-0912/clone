"""管理员后台：/api/admin/vector-dbs。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from ...admin_stats import list_clone_resource_stats
from ..conversions import admin_resource_to_api
from ..deps import AdminUser
from .. import paths

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
