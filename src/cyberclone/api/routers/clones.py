"""克隆人 CRUD：/api/clones[/...]。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from ..conversions import decode_upload_payload, profile_to_api
from ..deps import StoreDep

router = APIRouter(prefix="/api/clones", tags=["clones"])


@router.get("")
def list_clones(store: StoreDep) -> dict[str, Any]:
    return {"clones": [profile_to_api(profile) for profile in store.list_clones()]}


@router.post("", status_code=status.HTTP_201_CREATED)
def create_clone(payload: dict[str, Any] = Body(...), *, store: StoreDep) -> dict[str, Any]:
    try:
        upload = decode_upload_payload(payload)
        profile = store.create_clone(
            target_name=upload.target_name,
            chat_text=upload.chat_text,
            voice_files=[(file.filename, file.bytes) for file in upload.voice_files],
            image_files=[(file.filename, file.bytes) for file in upload.image_files],
            video_files=[(file.filename, file.bytes) for file in upload.video_files],
            sticker_files=[(file.filename, file.bytes) for file in upload.sticker_files],
            moments_files=[(file.filename, file.bytes) for file in upload.moments_files],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return {"clone": profile_to_api(profile)}


@router.get("/{clone_id}")
def get_clone(clone_id: str, store: StoreDep) -> dict[str, Any]:
    try:
        profile = store.load_clone(clone_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc
    return {"clone": profile_to_api(profile)}


@router.put("/{clone_id}")
def update_clone(
    clone_id: str,
    payload: dict[str, Any] = Body(...),
    *,
    store: StoreDep,
) -> dict[str, Any]:
    try:
        if "chatText" in payload:
            upload = decode_upload_payload(payload)
            profile = store.update_clone(
                clone_id,
                target_name=upload.target_name,
                chat_text=upload.chat_text,
                voice_files=[(file.filename, file.bytes) for file in upload.voice_files],
                image_files=[(file.filename, file.bytes) for file in upload.image_files],
                video_files=[(file.filename, file.bytes) for file in upload.video_files],
                sticker_files=[(file.filename, file.bytes) for file in upload.sticker_files],
                moments_files=[(file.filename, file.bytes) for file in upload.moments_files],
            )
        else:
            target_name = str(payload.get("targetName") or "").strip()
            if not target_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="targetName is required",
                )
            profile = store.update_clone(clone_id, target_name=target_name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    return {"clone": profile_to_api(profile)}


@router.delete("/{clone_id}")
def delete_clone(clone_id: str, store: StoreDep) -> dict[str, Any]:
    try:
        deleted = store.delete_clone(clone_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found")
    return {"ok": True, "cloneId": clone_id}
