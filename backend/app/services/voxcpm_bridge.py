from __future__ import annotations

import argparse
import base64
import binascii
from dataclasses import dataclass
import io
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
from threading import Lock
from typing import Any, Protocol


DEFAULT_MODEL_PATH = Path(
    "VoxCPM-local/models/models--openbmb--VoxCPM2/snapshots/"
    "bffb3df5a29440629464e5e839f4d214c8714c3d"
)

EMOTION_CONTROLS = {
    "natural": "自然，清晰，贴近日常对话",
    "calm": "平静，放松，语速稳定",
    "warm": "温柔，亲近，语气有耐心",
    "happy": "开心，明亮，语调上扬",
    "excited": "兴奋，有活力，语速稍快",
    "sad": "低落，轻声，语速放慢",
}


@dataclass(slots=True)
class SynthesisRequest:
    text: str
    emotion: str
    clone_id: str
    voice_name: str
    reference_audio_path: Path | None
    prompt_text: str
    control_prompt: str
    cfg_value: float = 2.0
    inference_steps: int = 4
    normalize: bool = False


class SynthesisEngine(Protocol):
    def synthesize(self, request: SynthesisRequest) -> bytes:
        raise NotImplementedError


def create_training_response(payload: dict[str, Any], storage_root: Path | None = None) -> dict[str, Any]:
    clone_id = _required_string(payload, "cloneId")
    sample_paths = _string_list(payload.get("samplePaths"))
    embedded_sample_paths = _write_embedded_audio_files(
        payload.get("sampleFiles"),
        clone_id=clone_id,
        storage_root=storage_root,
        subdir="training",
    )
    if embedded_sample_paths:
        sample_paths = [str(path) for path in embedded_sample_paths]
    if not sample_paths:
        raise ValueError("samplePaths must contain at least one voice sample path")

    sample_filenames = _string_list(payload.get("sampleFilenames"))
    if not sample_filenames:
        sample_filenames = [Path(path).name for path in sample_paths]

    return {
        "status": "ready",
        "adapter": "voxcpm-reference",
        "message": f"VoxCPM reference voice ready with {len(sample_paths)} sample(s).",
        "modelId": f"voxcpm-reference-{clone_id}",
        "jobId": f"local-reference-{clone_id}",
        "sampleCount": len(sample_paths),
        "sampleFilenames": sample_filenames,
        "samplePaths": sample_paths,
    }


def decode_synthesis_payload(payload: dict[str, Any], storage_root: Path | None = None) -> SynthesisRequest:
    text = _required_string(payload, "text")
    emotion = _optional_string(payload, "emotion") or "natural"
    reference_audio = _optional_string(payload, "referenceAudioPath")
    clone_id = _optional_string(payload, "cloneId")
    embedded_reference_path = _write_embedded_audio_file(
        payload.get("referenceAudioFile"),
        clone_id=clone_id or "unknown-clone",
        storage_root=storage_root,
        subdir="synthesis",
        fallback_name="reference.wav",
    )
    control_prompt = _optional_string(payload, "controlPrompt") or control_prompt_for_emotion(emotion)
    return SynthesisRequest(
        text=text,
        emotion=emotion,
        clone_id=clone_id,
        voice_name=_optional_string(payload, "voiceName"),
        reference_audio_path=embedded_reference_path or (Path(reference_audio) if reference_audio else None),
        prompt_text=_first_optional_string(payload, "promptText", "prompt_text", "referenceText", "reference_text"),
        control_prompt=control_prompt,
        cfg_value=_float_value(
            _first_present(payload, "cfgValue", "cfg_value"),
            2.0,
        ),
        inference_steps=_int_value(
            _first_present(payload, "inferenceSteps", "inference_steps", "inferenceTimesteps", "steps"),
            4,
        ),
        normalize=_bool_value(_first_present(payload, "normalize"), False),
    )


def create_synthesis_response(engine: SynthesisEngine, payload: dict[str, Any]) -> dict[str, Any]:
    request = decode_synthesis_payload(payload)
    wav_bytes = engine.synthesize(request)
    if not wav_bytes:
        raise ValueError("VoxCPM did not return audio bytes")
    return {
        "status": "ok",
        "message": "Speech synthesized by VoxCPM bridge.",
        "audioBase64": base64.b64encode(wav_bytes).decode("ascii"),
        "contentType": "audio/wav",
        "emotion": request.emotion,
    }


def control_prompt_for_emotion(emotion: str) -> str:
    return EMOTION_CONTROLS.get(emotion.strip().lower(), EMOTION_CONTROLS["natural"])


class VoxCPMEngine:
    def __init__(
        self,
        model_path: Path,
        device: str = "auto",
        zipenhancer_model_path: Path | None = None,
        enable_denoiser: bool = False,
        optimize: bool = False,
    ) -> None:
        self.model_path = model_path
        self.requested_device = device
        self.zipenhancer_model_path = zipenhancer_model_path
        self.enable_denoiser = enable_denoiser
        self.optimize = optimize
        self._model: Any | None = None
        self._load_lock = Lock()

    @property
    def device(self) -> str:
        if self.requested_device != "auto":
            return self.requested_device
        try:
            import torch
        except ImportError:
            return "cpu"
        return "cuda" if torch.cuda.is_available() else "cpu"

    def model(self) -> Any:
        if self._model is None:
            with self._load_lock:
                if self._model is None:
                    from voxcpm import VoxCPM

                    self._model = VoxCPM(
                        voxcpm_model_path=str(self.model_path),
                        zipenhancer_model_path=str(self.zipenhancer_model_path)
                        if self.zipenhancer_model_path
                        else None,
                        enable_denoiser=self.enable_denoiser,
                        optimize=self.optimize,
                        device=self.device,
                    )
        return self._model

    def synthesize(self, request: SynthesisRequest) -> bytes:
        model = self.model()
        final_text = f"({request.control_prompt}){request.text}" if request.control_prompt else request.text
        kwargs: dict[str, Any] = {
            "text": final_text,
            "reference_wav_path": str(request.reference_audio_path) if request.reference_audio_path else None,
            "cfg_value": request.cfg_value,
            "inference_timesteps": request.inference_steps,
            "normalize": request.normalize,
            "denoise": False,
        }
        if request.reference_audio_path and request.prompt_text:
            kwargs["prompt_wav_path"] = str(request.reference_audio_path)
            kwargs["prompt_text"] = request.prompt_text

        audio = model.generate(**kwargs)
        sample_rate = int(getattr(model.tts_model, "sample_rate", 16000))
        if isinstance(audio, tuple) and len(audio) == 2:
            sample_rate = int(audio[0])
            audio = audio[1]
        return _audio_to_wav_bytes(audio, sample_rate)


def create_handler(engine: SynthesisEngine) -> type[BaseHTTPRequestHandler]:
    class VoxCPMBridgeHandler(BaseHTTPRequestHandler):
        server_version = "VoxCPMBridge/0.1"

        def do_GET(self) -> None:  # noqa: N802 - http.server naming convention.
            if self.path == "/health":
                self._send_json({"ok": True})
                return
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802 - http.server naming convention.
            try:
                payload = self._read_json()
                if self.path in {"/train", "/api/train", "/voice/train"}:
                    self._send_json(create_training_response(payload))
                    return
                if self.path in {"/speak", "/tts", "/api/speak", "/api/tts"}:
                    self._send_json(create_synthesis_response(engine, payload))
                    return
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            except Exception as exc:  # noqa: BLE001 - normalize model failures for callers.
                self._send_json({"error": f"VoxCPM bridge failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
                return

            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0:
                raise ValueError("Request body is required")
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError as exc:
                raise ValueError("Request body must be JSON") from exc
            if not isinstance(payload, dict):
                raise ValueError("Request body must be a JSON object")
            return payload

        def _send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return VoxCPMBridgeHandler


def run_bridge(host: str, port: int, engine: SynthesisEngine) -> None:
    server = ThreadingHTTPServer((host, port), create_handler(engine))
    print(f"VoxCPM HTTP bridge running at http://{host}:{port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a VoxCPM HTTP bridge for Cyber Clone.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8810)
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"])
    parser.add_argument("--model-path", default=str(DEFAULT_MODEL_PATH))
    parser.add_argument("--zipenhancer-model-path", default="")
    parser.add_argument("--enable-denoiser", action="store_true")
    parser.add_argument("--optimize", action="store_true")
    args = parser.parse_args()

    engine = VoxCPMEngine(
        model_path=Path(args.model_path),
        device=args.device,
        zipenhancer_model_path=Path(args.zipenhancer_model_path) if args.zipenhancer_model_path else None,
        enable_denoiser=args.enable_denoiser,
        optimize=args.optimize,
    )
    run_bridge(args.host, args.port, engine)


def _audio_to_wav_bytes(audio: Any, sample_rate: int) -> bytes:
    if isinstance(audio, bytes):
        return audio

    import soundfile as sf

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV")
    return buffer.getvalue()


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} is required")
    return value.strip()


def _optional_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    return value.strip() if isinstance(value, str) else ""


def _first_optional_string(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _optional_string(payload, key)
        if value:
            return value
    return ""


def _first_present(payload: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _write_embedded_audio_files(
    value: Any,
    clone_id: str,
    storage_root: Path | None,
    subdir: str,
) -> list[Path]:
    if not isinstance(value, list):
        return []

    paths = []
    for index, item in enumerate(value, start=1):
        path = _write_embedded_audio_file(
            item,
            clone_id=clone_id,
            storage_root=storage_root,
            subdir=subdir,
            fallback_name=f"sample-{index}.wav",
        )
        if path is not None:
            paths.append(path)
    return paths


def _write_embedded_audio_file(
    value: Any,
    clone_id: str,
    storage_root: Path | None,
    subdir: str,
    fallback_name: str,
) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError(f"{subdir} audio file entries must be JSON objects")

    data = value.get("data")
    wav_bytes = _decode_data_url(data, f"{subdir} audio data")
    filename = _safe_filename(value.get("name"), fallback_name)
    target_dir = _bridge_storage_root(storage_root) / _safe_path_segment(clone_id, "unknown-clone") / subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = _unique_path(target_dir / filename)
    target_path.write_bytes(wav_bytes)
    return target_path


def _decode_data_url(value: Any, label: str) -> bytes:
    if not isinstance(value, str) or not value.startswith("data:"):
        raise ValueError(f"{label} must be a base64 data URL")
    header, separator, encoded = value.partition(",")
    if not separator or ";base64" not in header.lower():
        raise ValueError(f"{label} must be a base64 data URL")
    try:
        decoded = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"{label} is not valid base64") from exc
    if not decoded:
        raise ValueError(f"{label} is empty")
    return decoded


def _bridge_storage_root(storage_root: Path | None) -> Path:
    return storage_root or Path(tempfile.gettempdir()) / "cyberclone-voxcpm-bridge"


def _safe_filename(value: Any, fallback: str) -> str:
    name = Path(str(value or fallback)).name.strip()
    return name if name not in {"", ".", ".."} else fallback


def _safe_path_segment(value: str, fallback: str) -> str:
    cleaned = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in value.strip())
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path

    suffix = path.suffix
    stem = path.stem
    for index in range(2, 1000):
        candidate = path.with_name(f"{stem}-{index}{suffix}")
        if not candidate.exists():
            return candidate
    raise ValueError(f"Could not allocate a unique filename for {path.name}")


def _float_value(value: Any, default: float) -> float:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int_value(value: Any, default: int) -> int:
    if value is None or value == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _bool_value(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return default


if __name__ == "__main__":
    main()
