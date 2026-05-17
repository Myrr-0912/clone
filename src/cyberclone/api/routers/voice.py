"""语音相关：/api/clones/{id}/voice/{status,samples,train}。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from ... import voice as voice_module
from ..conversions import decode_voice_samples_payload, profile_to_api
from ..deps import StoreDep
from .. import paths

router = APIRouter(prefix="/api/clones/{clone_id}/voice", tags=["voice"])


@router.get("/status")
def get_status(clone_id: str, store: StoreDep) -> dict[str, Any]:
    try:
        profile = store.load_clone(clone_id)
        current = store.load_voice_status(clone_id)
        refreshed = voice_module.refresh_voice_training_status(
            profile, current, env_path=paths.env_path()
        )
        if refreshed != current:
            store.update_voice_status(clone_id, refreshed)
            profile.voice = refreshed
            current = refreshed
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    return {"voice": asdict(current), "clone": profile_to_api(profile)}


@router.post("/samples", status_code=status.HTTP_201_CREATED)
def add_samples(
    clone_id: str,
    payload: dict[str, Any] = Body(...),
    *,
    store: StoreDep,
) -> dict[str, Any]:
    try:
        voice_files = decode_voice_samples_payload(payload)
        profile = store.add_voice_samples(
            clone_id,
            [(file.filename, file.bytes) for file in voice_files],
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    return {
        "voice": asdict(profile.voice) if profile.voice else None,
        "clone": profile_to_api(profile),
    }


@router.post("/train")
def train(clone_id: str, store: StoreDep) -> dict[str, Any]:
    try:
        profile = store.load_clone(clone_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    try:
        status_obj = voice_module.train_voice_model(
            profile=profile,
            sample_paths=store.voice_sample_paths(clone_id),
            env_path=paths.env_path(),
        )
        store.update_voice_status(clone_id, status_obj)
        profile.voice = status_obj
    except Exception as exc:  # noqa: BLE001 - normalize voice adapter failures for the UI.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Voice training failed: {exc}",
        ) from exc

    return {"voice": asdict(status_obj), "clone": profile_to_api(profile)}
