"""请求体解码与领域对象 → API JSON 的纯函数。

从旧 web.py 抽出，方便 FastAPI router 和单元测试共用。
"""

from __future__ import annotations

import base64
from dataclasses import asdict, dataclass
from pathlib import Path

from ..models import CloneProfile
from ..voice import SpeechSynthesisResult


@dataclass(slots=True)
class UploadedFile:
    filename: str
    bytes: bytes


@dataclass(slots=True)
class UploadPayload:
    target_name: str
    chat_text: str
    voice_files: list[UploadedFile]
    image_files: list[UploadedFile]
    video_files: list[UploadedFile]
    sticker_files: list[UploadedFile]
    moments_files: list[UploadedFile]

    @property
    def voice_filename(self) -> str:
        return self.voice_files[0].filename if self.voice_files else ""

    @property
    def voice_bytes(self) -> bytes:
        return self.voice_files[0].bytes if self.voice_files else b""


@dataclass(slots=True)
class SpeechPayload:
    text: str
    emotion: str = "natural"
    inference_steps: int | None = None
    cfg_value: float | None = None


def decode_upload_payload(payload: dict[str, object]) -> UploadPayload:
    target_name = _required_string(payload, "targetName")
    chat_text = _required_string(payload, "chatText")
    voice_files = _decode_uploaded_files(payload.get("voiceFiles"), "voiceFiles")
    voice_filename = _optional_string(payload, "voiceName")
    voice_data = _optional_string(payload, "voiceData")
    if voice_filename or voice_data:
        if bool(voice_filename) != bool(voice_data):
            raise ValueError("voiceName and voiceData must be provided together")
        voice_files.append(
            UploadedFile(
                filename=Path(voice_filename).name,
                bytes=_decode_base64_file(voice_data, "voiceData"),
            )
        )
    image_files = _decode_uploaded_files(payload.get("imageFiles"), "imageFiles")
    video_files = _decode_uploaded_files(payload.get("videoFiles"), "videoFiles")
    sticker_files = _decode_uploaded_files(payload.get("stickerFiles"), "stickerFiles")
    moments_files = _decode_uploaded_files(payload.get("momentsFiles"), "momentsFiles")

    return UploadPayload(
        target_name=target_name,
        chat_text=chat_text,
        voice_files=voice_files,
        image_files=image_files,
        video_files=video_files,
        sticker_files=sticker_files,
        moments_files=moments_files,
    )


def decode_speech_payload(payload: dict[str, object]) -> SpeechPayload:
    return SpeechPayload(
        text=_required_string(payload, "text"),
        emotion=_optional_string(payload, "emotion") or "natural",
        inference_steps=_optional_positive_int(payload, "inferenceSteps"),
        cfg_value=_optional_positive_float(payload, "cfgValue"),
    )


def decode_voice_samples_payload(payload: dict[str, object]) -> list[UploadedFile]:
    voice_files = _decode_uploaded_files(payload.get("voiceFiles"), "voiceFiles")
    voice_filename = _optional_string(payload, "voiceName")
    voice_data = _optional_string(payload, "voiceData")
    if voice_filename or voice_data:
        if bool(voice_filename) != bool(voice_data):
            raise ValueError("voiceName and voiceData must be provided together")
        voice_files.append(
            UploadedFile(
                filename=Path(voice_filename).name,
                bytes=_decode_base64_file(voice_data, "voiceData"),
            )
        )

    if not voice_files:
        raise ValueError("voiceFiles must contain at least one voice sample")
    return voice_files


def profile_to_api(profile: CloneProfile) -> dict[str, object]:
    return {
        "cloneId": profile.clone_id,
        "name": profile.name,
        "style": {
            "catchphrases": profile.style.catchphrases,
            "particles": profile.style.particles,
            "punctuation": profile.style.punctuation,
            "emoji_style": profile.style.emoji_style,
            "message_format": profile.style.message_format,
            "typing_habits": profile.style.typing_habits,
            "address_terms": profile.style.address_terms,
            "example_dialogues": profile.style.example_dialogues,
            "average_length": profile.style.average_length,
        },
        "memory": {
            "keyTopics": profile.memory.key_topics,
            "key_topics": profile.memory.key_topics,
            "summary": profile.memory.summary,
            "relationship_overview": profile.memory.relationship_overview,
            "timeline": profile.memory.timeline,
            "daily_patterns": profile.memory.daily_patterns,
            "shared_experiences": profile.memory.shared_experiences,
            "inside_jokes": profile.memory.inside_jokes,
            "food_preferences": profile.memory.food_preferences,
            "interests": profile.memory.interests,
            "conflict_patterns": profile.memory.conflict_patterns,
            "sweet_moments": profile.memory.sweet_moments,
            "breakup_notes": profile.memory.breakup_notes,
        },
        "rules": asdict(profile.rules),
        "corrections": profile.corrections,
        "sourceStats": profile.source_stats,
        "voice": asdict(profile.voice) if profile.voice else None,
    }


def speech_to_api(speech: SpeechSynthesisResult) -> dict[str, object]:
    return {
        "status": speech.status,
        "backend": speech.backend,
        "message": speech.message,
        "audioDataUrl": speech.audio_data_url,
        "contentType": speech.content_type,
        "emotion": speech.emotion,
    }


def admin_resource_to_api(item: dict[str, object]) -> dict[str, object]:
    vector_size = int(item.get("vectorDbSizeBytes") or 0)
    voice_size = int(item.get("voiceModelSizeBytes") or 0)
    chunk_count = int(item.get("vectorChunkCount") or item.get("chunkCount") or 0)
    return {
        **item,
        "chunkCount": chunk_count,
        "vectorDbSizeBytes": vector_size,
        "voiceModelSizeBytes": voice_size,
        "voiceModelStatus": item.get("voiceStatus") or item.get("voiceModelStatus") or "",
    }


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if isinstance(value, str):
        return value.strip()
    return ""


def _optional_positive_int(payload: dict[str, object], key: str) -> int | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return parsed


def _optional_positive_float(payload: dict[str, object], key: str) -> float | None:
    value = payload.get(key)
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{key} must be a positive number") from exc
    if parsed <= 0:
        raise ValueError(f"{key} must be a positive number")
    return parsed


def _decode_uploaded_files(value: object, field_name: str) -> list[UploadedFile]:
    if value in (None, ""):
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")

    files: list[UploadedFile] = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"{field_name} must contain file objects")
        filename = Path(_required_string(item, "name")).name
        files.append(
            UploadedFile(
                filename=filename,
                bytes=_decode_base64_file(_required_string(item, "data"), f"{field_name}.data"),
            )
        )
    return files


def _decode_base64_file(value: str, field_name: str) -> bytes:
    encoded = value.split(",", 1)[1] if "," in value else value
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except Exception as exc:  # noqa: BLE001 - normalize parsing errors for the API.
        raise ValueError(f"{field_name} must be valid base64") from exc

    if not decoded:
        raise ValueError(f"{field_name} cannot be empty")
    return decoded


def first_voice_sample_path(store, clone_id: str) -> Path | None:
    sample_paths = store.voice_sample_paths(clone_id)
    return sample_paths[0] if sample_paths else None
