from __future__ import annotations

import base64
from dataclasses import dataclass
import io
import json
import math
import mimetypes
import os
from pathlib import Path
from typing import Mapping, MutableMapping, Sequence
from uuid import uuid4
from urllib import error, request
from urllib.parse import urlparse
import wave

from app.models.clone import CloneProfile, VoiceTrainingStatus


@dataclass(slots=True)
class SpeechSynthesisResult:
    status: str
    backend: str
    message: str
    audio_data_url: str | None = None
    content_type: str = "audio/wav"
    emotion: str = "natural"


def create_voice_training_status(sample_filenames: str | Sequence[str] | None) -> VoiceTrainingStatus:
    filenames = _clean_sample_filenames(sample_filenames)
    if not filenames:
        return VoiceTrainingStatus(
            status="missing_samples",
            adapter="reference_tts",
            sample_filename=None,
            sample_filenames=[],
            sample_count=0,
            message="No voice sample uploaded; voice mode will use text fallback until samples are added.",
        )

    return VoiceTrainingStatus(
        status="samples_ready",
        adapter="reference_tts",
        sample_filename=filenames[0],
        sample_filenames=filenames,
        sample_count=len(filenames),
        message=(
            f"Saved {len(filenames)} voice sample(s). Configure VOICE_TTS_BACKEND to synthesize replies."
        ),
    )


def synthesize_speech(
    profile: CloneProfile,
    text: str,
    reference_audio_path: Path | None,
    emotion: str = "natural",
    inference_steps: int | None = None,
    cfg_value: float | None = None,
    env: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> SpeechSynthesisResult:
    source = dict(os.environ if env is None else env)
    if env_path is not None:
        _load_env_file(env_path, source)

    text = text.strip()
    emotion = emotion.strip() or "natural"
    if not text:
        return SpeechSynthesisResult(
            status="error",
            backend="none",
            message="Speech text is required.",
            emotion=emotion,
        )

    backend = source.get("VOICE_TTS_BACKEND", "").strip().lower()
    if not backend:
        return SpeechSynthesisResult(
            status="unavailable",
            backend="none",
            message="VOICE_TTS_BACKEND is not configured; returning text-only voice fallback.",
            emotion=emotion,
        )

    if backend == "mock":
        return SpeechSynthesisResult(
            status="ok",
            backend="mock",
            message="Generated a local verification tone instead of model speech.",
            audio_data_url=_wav_data_url(_generate_mock_wav(emotion)),
            emotion=emotion,
        )

    if backend in {"http", "voxcpm-http", "voxcpm"}:
        return _synthesize_http(
            profile,
            text,
            reference_audio_path,
            emotion,
            backend,
            source,
            inference_steps=inference_steps,
            cfg_value=cfg_value,
        )

    return SpeechSynthesisResult(
        status="error",
        backend=backend,
        message=f"Unsupported VOICE_TTS_BACKEND: {backend}",
        emotion=emotion,
    )


def train_voice_model(
    profile: CloneProfile,
    sample_paths: Sequence[Path],
    env: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> VoiceTrainingStatus:
    source = dict(os.environ if env is None else env)
    if env_path is not None:
        _load_env_file(env_path, source)

    sample_names = _clean_sample_filenames([path.name for path in sample_paths])
    if not sample_names:
        return VoiceTrainingStatus(
            status="missing_samples",
            adapter="none",
            message="Upload voice samples before starting voice model training.",
            sample_filename=None,
            sample_filenames=[],
            sample_count=0,
            error="missing_samples",
        )

    backend = source.get("VOICE_TRAINING_BACKEND", "").strip().lower()
    if not backend:
        return VoiceTrainingStatus(
            status="pending_backend",
            adapter="none",
            message="VOICE_TRAINING_BACKEND is not configured; samples are saved but no training job was started.",
            sample_filename=sample_names[0],
            sample_filenames=sample_names,
            sample_count=len(sample_names),
            error="backend_unconfigured",
        )

    if backend == "mock":
        return VoiceTrainingStatus(
            status="ready",
            adapter="mock",
            message="Mock voice model is ready for local verification.",
            sample_filename=sample_names[0],
            sample_filenames=sample_names,
            sample_count=len(sample_names),
            model_id=f"mock-{profile.clone_id}-{uuid4().hex[:8]}",
        )

    if backend in {"http", "voxcpm-http", "voxcpm"}:
        return _train_http(profile, sample_paths, sample_names, backend, source)

    return VoiceTrainingStatus(
        status="pending_adapter",
        adapter=backend,
        message=f"Voice training backend '{backend}' is reserved for an external training worker.",
        sample_filename=sample_names[0],
        sample_filenames=sample_names,
        sample_count=len(sample_names),
        error="adapter_not_implemented",
    )


def refresh_voice_training_status(
    profile: CloneProfile,
    current: VoiceTrainingStatus,
    env: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> VoiceTrainingStatus:
    if current.status not in {"queued", "running"}:
        return current

    source = dict(os.environ if env is None else env)
    if env_path is not None:
        _load_env_file(env_path, source)

    backend = source.get("VOICE_TRAINING_BACKEND", "").strip().lower() or current.adapter
    if backend not in {"http", "voxcpm-http", "voxcpm"}:
        return current

    url = source.get("VOICE_TRAINING_STATUS_URL") or source.get("VOXCPM_TRAINING_STATUS_URL")
    if not url:
        return current

    headers = {"Content-Type": "application/json"}
    api_key = source.get("VOICE_TRAINING_API_KEY") or source.get("VOICE_TTS_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "cloneId": profile.clone_id,
        "voiceName": profile.name,
        "jobId": current.job_id or "",
        "modelId": current.model_id or "",
    }

    timeout = _float_env(
        source.get("VOICE_TRAINING_STATUS_TIMEOUT_SECONDS") or source.get("VOICE_TRAINING_TIMEOUT_SECONDS"),
        30.0,
    )
    try:
        response = _post_json(url, headers, payload, timeout)
    except RuntimeError as exc:
        return VoiceTrainingStatus(
            status="error",
            adapter=backend,
            message=str(exc),
            sample_filename=current.sample_filename,
            sample_filenames=list(current.sample_filenames),
            sample_count=current.sample_count,
            error="status_request_failed",
            model_id=current.model_id,
            job_id=current.job_id,
        )

    status = str(response.get("status") or current.status)
    message = str(response.get("message") or current.message)
    error_value = response.get("error")
    error_text = error_value.strip() if isinstance(error_value, str) and error_value.strip() else None
    if status in {"error", "failed"} and not error_text:
        error_text = "training_failed"

    return VoiceTrainingStatus(
        status=status,
        adapter=str(response.get("adapter") or backend),
        message=message,
        sample_filename=current.sample_filename,
        sample_filenames=list(current.sample_filenames),
        sample_count=current.sample_count,
        error=error_text,
        model_id=_optional_response_string(response, "modelId", "model_id") or current.model_id,
        job_id=_optional_response_string(response, "jobId", "job_id") or current.job_id,
    )


def _clean_sample_filenames(sample_filenames: str | Sequence[str] | None) -> list[str]:
    if sample_filenames is None:
        raw_names: Sequence[str] = []
    elif isinstance(sample_filenames, str):
        raw_names = [sample_filenames]
    else:
        raw_names = sample_filenames

    cleaned = []
    for filename in raw_names:
        name = Path(str(filename)).name.strip()
        if name:
            cleaned.append(name)
    return cleaned


def _train_http(
    profile: CloneProfile,
    sample_paths: Sequence[Path],
    sample_names: list[str],
    backend: str,
    env: Mapping[str, str],
) -> VoiceTrainingStatus:
    url = env.get("VOICE_TRAINING_URL") or env.get("VOXCPM_TRAINING_URL")
    if not url:
        return VoiceTrainingStatus(
            status="error",
            adapter=backend,
            message="VOICE_TRAINING_URL or VOXCPM_TRAINING_URL is required for voice training.",
            sample_filename=sample_names[0],
            sample_filenames=sample_names,
            sample_count=len(sample_names),
            error="missing_training_url",
        )

    headers = {"Content-Type": "application/json"}
    api_key = env.get("VOICE_TRAINING_API_KEY") or env.get("VOICE_TTS_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "cloneId": profile.clone_id,
        "voiceName": profile.name,
        "samplePaths": [str(path) for path in sample_paths],
        "sampleFilenames": sample_names,
        "style": {
            "catchphrases": profile.style.catchphrases,
            "punctuation": profile.style.punctuation,
            "averageLength": profile.style.average_length,
        },
    }
    if _optional_bool_env(env.get("VOICE_TRAINING_INCLUDE_AUDIO")) is True:
        payload["sampleFiles"] = _sample_files_payload(sample_paths)

    try:
        response = _post_json(url, headers, payload, _float_env(env.get("VOICE_TRAINING_TIMEOUT_SECONDS"), 120.0))
    except RuntimeError as exc:
        return VoiceTrainingStatus(
            status="error",
            adapter=backend,
            message=str(exc),
            sample_filename=sample_names[0],
            sample_filenames=sample_names,
            sample_count=len(sample_names),
            error="training_request_failed",
        )

    status = str(response.get("status") or "ready")
    message = str(response.get("message") or "Voice training request accepted.")
    error_value = response.get("error")
    error_text = error_value.strip() if isinstance(error_value, str) and error_value.strip() else None
    if status in {"error", "failed"} and not error_text:
        error_text = "training_failed"

    return VoiceTrainingStatus(
        status=status,
        adapter=backend,
        message=message,
        sample_filename=sample_names[0],
        sample_filenames=sample_names,
        sample_count=len(sample_names),
        error=error_text,
        model_id=_optional_response_string(response, "modelId", "model_id"),
        job_id=_optional_response_string(response, "jobId", "job_id"),
    )


def _synthesize_http(
    profile: CloneProfile,
    text: str,
    reference_audio_path: Path | None,
    emotion: str,
    backend: str,
    env: Mapping[str, str],
    *,
    inference_steps: int | None = None,
    cfg_value: float | None = None,
) -> SpeechSynthesisResult:
    url = env.get("VOICE_TTS_URL") or env.get("VOXCPM_TTS_URL")
    if not url:
        return SpeechSynthesisResult(
            status="unavailable",
            backend=backend,
            message="VOICE_TTS_URL or VOXCPM_TTS_URL is required for HTTP speech synthesis.",
            emotion=emotion,
        )

    voice = profile.voice
    if reference_audio_path is None and not (voice and voice.model_id):
        return SpeechSynthesisResult(
            status="unavailable",
            backend=backend,
            message="Upload a voice sample or train a voice model before HTTP speech synthesis.",
            emotion=emotion,
        )

    payload = {
        "text": text,
        "emotion": emotion,
        "cloneId": profile.clone_id,
        "voiceName": profile.name,
        "referenceAudioPath": str(reference_audio_path) if reference_audio_path else "",
        "modelId": voice.model_id if voice and voice.model_id else "",
        "jobId": voice.job_id if voice and voice.job_id else "",
        "voiceStatus": voice.status if voice else "",
        "voiceAdapter": voice.adapter if voice else "",
        "sampleFilenames": list(voice.sample_filenames) if voice else [],
        "sampleCount": voice.sample_count if voice else 0,
        "style": {
            "catchphrases": profile.style.catchphrases,
            "punctuation": profile.style.punctuation,
            "averageLength": profile.style.average_length,
        },
    }
    control_prompt = _tts_control_prompt(env, emotion)
    if control_prompt:
        payload["controlPrompt"] = control_prompt

    effective_cfg_value = cfg_value if cfg_value is not None else _optional_float_env(env.get("VOICE_TTS_CFG_VALUE"))
    if effective_cfg_value is not None:
        payload["cfgValue"] = effective_cfg_value

    effective_inference_steps = (
        inference_steps if inference_steps is not None else _optional_int_env(env.get("VOICE_TTS_INFERENCE_STEPS"))
    )
    if effective_inference_steps is not None:
        payload["inferenceSteps"] = effective_inference_steps

    normalize = _optional_bool_env(env.get("VOICE_TTS_NORMALIZE"))
    if normalize is not None:
        payload["normalize"] = normalize

    if _optional_bool_env(env.get("VOICE_TTS_INCLUDE_REFERENCE_AUDIO")) is True and reference_audio_path is not None:
        payload["referenceAudioFile"] = _audio_file_payload(reference_audio_path)

    headers = {"Content-Type": "application/json"}
    api_key = env.get("VOICE_TTS_API_KEY", "")
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        response = _post_json(url, headers, payload, _float_env(env.get("VOICE_TTS_TIMEOUT_SECONDS"), 60.0))
    except RuntimeError as exc:
        return SpeechSynthesisResult(
            status="error",
            backend=backend,
            message=str(exc),
            emotion=emotion,
        )

    content_type = str(response.get("contentType") or response.get("content_type") or "audio/wav")
    audio_data_url = response.get("audioDataUrl") or response.get("audio_data_url")
    if isinstance(audio_data_url, str) and audio_data_url.startswith("data:"):
        return SpeechSynthesisResult(
            status="ok",
            backend=backend,
            message=str(response.get("message") or "Speech synthesized."),
            audio_data_url=audio_data_url,
            content_type=content_type,
            emotion=emotion,
        )

    audio_base64 = response.get("audioBase64") or response.get("audio_base64")
    if isinstance(audio_base64, str) and audio_base64:
        return SpeechSynthesisResult(
            status="ok",
            backend=backend,
            message=str(response.get("message") or "Speech synthesized."),
            audio_data_url=f"data:{content_type};base64,{audio_base64}",
            content_type=content_type,
            emotion=emotion,
        )

    backend_status = _optional_response_string(response, "status")
    backend_error = _optional_response_string(response, "error")
    if backend_error or (backend_status and backend_status.lower() in {"error", "failed", "unavailable"}):
        return SpeechSynthesisResult(
            status=backend_status or "error",
            backend=backend,
            message=_combine_backend_message(response) or "Speech backend failed without returning audio.",
            content_type=content_type,
            emotion=emotion,
        )

    return SpeechSynthesisResult(
        status="error",
        backend=backend,
        message="Speech backend did not return audioDataUrl or audioBase64.",
        content_type=content_type,
        emotion=emotion,
    )


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        opener = _proxy_bypassing_opener(url)
        response_context = opener.open(req, timeout=timeout) if opener else request.urlopen(req, timeout=timeout)
        with response_context as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = _format_http_error_detail(exc.read())
        raise RuntimeError(f"Speech API request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"Speech API request failed: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Speech API response was not valid JSON") from exc

    if not isinstance(decoded, dict):
        raise RuntimeError("Speech API response must be a JSON object")
    return decoded


def _proxy_bypassing_opener(url: str):
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").strip().lower()
    if hostname in {"127.0.0.1", "localhost", "::1"}:
        return request.build_opener(request.ProxyHandler({}))
    return None


def _optional_response_string(response: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        value = response.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _combine_backend_message(response: dict[str, object]) -> str:
    message = _optional_response_string(response, "message") or ""
    error_text = _optional_response_string(response, "error") or ""
    if message and error_text and error_text not in message:
        return f"{message} ({error_text})"
    return message or error_text


def _format_http_error_detail(body: bytes) -> str:
    decoded = body.decode("utf-8", errors="replace").strip()
    if not decoded:
        return "empty response body"
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError:
        return decoded
    if isinstance(payload, dict):
        return _combine_backend_message(payload) or decoded
    return decoded


def _sample_files_payload(sample_paths: Sequence[Path]) -> list[dict[str, str]]:
    return [_audio_file_payload(path) for path in sample_paths]


def _audio_file_payload(path: Path) -> dict[str, str]:
    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return {
        "name": path.name,
        "contentType": content_type,
        "data": f"data:{content_type};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}",
    }


def _tts_control_prompt(env: Mapping[str, str], emotion: str) -> str:
    suffix = _env_key_suffix(emotion)
    specific = env.get(f"VOICE_TTS_CONTROL_PROMPT_{suffix}", "").strip()
    if specific:
        return specific
    return env.get("VOICE_TTS_CONTROL_PROMPT", "").strip()


def _env_key_suffix(value: str) -> str:
    suffix = "".join(char if char.isalnum() else "_" for char in value.upper()).strip("_")
    return suffix or "NATURAL"


def _generate_mock_wav(emotion: str) -> bytes:
    sample_rate = 16000
    duration_seconds = 0.32
    frequency = {
        "calm": 330.0,
        "sad": 294.0,
        "warm": 392.0,
        "happy": 523.25,
        "excited": 659.25,
    }.get(emotion.lower(), 440.0)
    frames = bytearray()
    total_samples = int(sample_rate * duration_seconds)
    for index in range(total_samples):
        envelope = min(1.0, index / 400) * min(1.0, (total_samples - index) / 400)
        sample = int(math.sin(2 * math.pi * frequency * index / sample_rate) * 32767 * 0.18 * envelope)
        frames.extend(sample.to_bytes(2, byteorder="little", signed=True))

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))
    return buffer.getvalue()


def _wav_data_url(wav_bytes: bytes) -> str:
    return f"data:audio/wav;base64,{base64.b64encode(wav_bytes).decode('ascii')}"


def _load_env_file(path: Path, env: MutableMapping[str, str]) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in env:
            continue
        env[key] = _strip_quotes(value.strip())


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _float_env(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _optional_float_env(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _optional_int_env(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _optional_bool_env(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    lowered = value.strip().lower()
    if lowered in {"true", "1", "yes", "on"}:
        return True
    if lowered in {"false", "0", "no", "off"}:
        return False
    return None
