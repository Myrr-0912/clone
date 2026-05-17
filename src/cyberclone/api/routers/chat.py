"""聊天 + 语音合成：/api/clones/{id}/{chat,speak}。"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Body, HTTPException, status

from ...chat_engine import extract_text_correction
from ...llm import create_chat_engine
from ...models import ChatReply
from ...voice import synthesize_speech
from ..conversions import (
    decode_speech_payload,
    first_voice_sample_path,
    profile_to_api,
    speech_to_api,
)
from ..deps import StoreDep
from .. import paths

router = APIRouter(prefix="/api/clones/{clone_id}", tags=["chat"])


@router.post("/chat")
def chat(
    clone_id: str,
    payload: dict[str, Any] = Body(...),
    *,
    store: StoreDep,
) -> dict[str, Any]:
    message = str(payload.get("message") or "").strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message is required")

    try:
        profile = store.load_clone(clone_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    correction = extract_text_correction(message)
    if correction:
        try:
            profile = store.add_text_correction(clone_id, correction)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
            ) from exc

        reply = ChatReply(
            clone_id=profile.clone_id,
            text="我记住了，后面会按这个调整。",
            emotion="calm",
        )
        return {"reply": asdict(reply), "clone": profile_to_api(profile)}

    try:
        retrieved_context = store.retrieve_chat_context(clone_id, message)
        reply = create_chat_engine(paths.env_path()).reply(
            profile,
            message,
            retrieved_context=retrieved_context,
        )
    except Exception as exc:  # noqa: BLE001 - surface LLM integration failures to the UI.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM reply failed: {exc}",
        ) from exc

    return {"reply": asdict(reply)}


@router.post("/speak")
def speak(
    clone_id: str,
    payload: dict[str, Any] = Body(...),
    *,
    store: StoreDep,
) -> dict[str, Any]:
    try:
        speech_payload = decode_speech_payload(payload)
        profile = store.load_clone(clone_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found") from exc

    try:
        speech = synthesize_speech(
            profile=profile,
            text=speech_payload.text,
            reference_audio_path=first_voice_sample_path(store, clone_id),
            emotion=speech_payload.emotion,
            inference_steps=speech_payload.inference_steps,
            cfg_value=speech_payload.cfg_value,
            env_path=paths.env_path(),
        )
    except Exception as exc:  # noqa: BLE001 - normalize voice adapter failures for the UI.
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Speech synthesis failed: {exc}",
        ) from exc

    return {"speech": speech_to_api(speech)}
