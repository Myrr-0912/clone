from __future__ import annotations

import argparse
import base64
from dataclasses import asdict, dataclass
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .chat_engine import extract_text_correction
from .llm import create_chat_engine
from .models import ChatReply, CloneProfile
from .storage import CloneStore
from .voice import SpeechSynthesisResult, refresh_voice_training_status, synthesize_speech, train_voice_model

PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEB_ROOT = PROJECT_ROOT / "web"
DATA_ROOT = PROJECT_ROOT / "data" / "clones"


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
        "style": asdict(profile.style),
        "memory": asdict(profile.memory),
        "sourceStats": profile.source_stats,
        "voice": asdict(profile.voice) if profile.voice else None,
    }


class CloneRequestHandler(BaseHTTPRequestHandler):
    server_version = "CyberCloneMVP/0.1"

    def do_GET(self) -> None:  # noqa: N802 - http.server naming convention.
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path.startswith("/api/clones/") and parsed.path.endswith("/voice/status"):
            self._handle_get_voice_status(parsed.path)
            return
        if parsed.path.startswith("/api/clones/"):
            self._handle_get_clone(parsed.path)
            return
        self._serve_static(parsed.path)

    def do_POST(self) -> None:  # noqa: N802 - http.server naming convention.
        parsed = urlparse(self.path)
        if parsed.path == "/api/clones":
            self._handle_create_clone()
            return
        if parsed.path.startswith("/api/clones/") and parsed.path.endswith("/voice/samples"):
            self._handle_upload_voice_samples(parsed.path)
            return
        if parsed.path.startswith("/api/clones/") and parsed.path.endswith("/voice/train"):
            self._handle_train_voice(parsed.path)
            return
        if parsed.path.startswith("/api/clones/") and parsed.path.endswith("/chat"):
            self._handle_chat(parsed.path)
            return
        if parsed.path.startswith("/api/clones/") and parsed.path.endswith("/speak"):
            self._handle_speak(parsed.path)
            return
        self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _handle_create_clone(self) -> None:
        try:
            upload = decode_upload_payload(self._read_json())
            profile = self._store().create_clone(
                target_name=upload.target_name,
                chat_text=upload.chat_text,
                voice_files=[(file.filename, file.bytes) for file in upload.voice_files],
                image_files=[(file.filename, file.bytes) for file in upload.image_files],
                video_files=[(file.filename, file.bytes) for file in upload.video_files],
                sticker_files=[(file.filename, file.bytes) for file in upload.sticker_files],
                moments_files=[(file.filename, file.bytes) for file in upload.moments_files],
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return

        self._send_json({"clone": profile_to_api(profile)}, HTTPStatus.CREATED)

    def _handle_upload_voice_samples(self, path: str) -> None:
        clone_id = _clone_id_from_path(path.removesuffix("/voice/samples"))
        store = self._store()
        try:
            voice_files = decode_voice_samples_payload(self._read_json())
            profile = store.add_voice_samples(
                clone_id,
                [(file.filename, file.bytes) for file in voice_files],
            )
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return

        self._send_json(
            {"voice": asdict(profile.voice) if profile.voice else None, "clone": profile_to_api(profile)},
            HTTPStatus.CREATED,
        )

    def _handle_get_clone(self, path: str) -> None:
        if len(_path_parts(path)) != 3:
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return
        clone_id = _clone_id_from_path(path)
        try:
            profile = self._store().load_clone(clone_id)
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"clone": profile_to_api(profile)})

    def _handle_get_voice_status(self, path: str) -> None:
        try:
            clone_id = _clone_id_from_path(path.removesuffix("/voice/status"))
        except ValueError:
            self._send_json({"error": "Clone id is required"}, HTTPStatus.BAD_REQUEST)
            return
        store = self._store()
        try:
            profile = store.load_clone(clone_id)
            status = store.load_voice_status(clone_id)
            refreshed = refresh_voice_training_status(profile, status, env_path=PROJECT_ROOT / ".env")
            if refreshed != status:
                store.update_voice_status(clone_id, refreshed)
                profile.voice = refreshed
                status = refreshed
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return
        self._send_json({"voice": asdict(status), "clone": profile_to_api(profile)})

    def _handle_chat(self, path: str) -> None:
        clone_id = _clone_id_from_path(path.removesuffix("/chat"))
        try:
            message = _required_string(self._read_json(), "message")
            store = self._store()
            profile = store.load_clone(clone_id)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return

        correction = extract_text_correction(message)
        if correction:
            try:
                profile = store.add_text_correction(clone_id, correction)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
                return
            reply = ChatReply(
                clone_id=profile.clone_id,
                text="我记住了，后面会按这个调整。",
                emotion="calm",
            )
            self._send_json({"reply": asdict(reply), "clone": profile_to_api(profile)})
            return

        try:
            reply = create_chat_engine(PROJECT_ROOT / ".env").reply(profile, message)
        except Exception as exc:  # noqa: BLE001 - surface LLM integration failures to the UI.
            self._send_json({"error": f"LLM reply failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"reply": asdict(reply)})

    def _handle_speak(self, path: str) -> None:
        clone_id = _clone_id_from_path(path.removesuffix("/speak"))
        try:
            payload = decode_speech_payload(self._read_json())
            profile = self._store().load_clone(clone_id)
        except ValueError as exc:
            self._send_json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            return
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            speech = synthesize_speech(
                profile=profile,
                text=payload.text,
                reference_audio_path=_first_voice_sample_path(profile),
                emotion=payload.emotion,
                env_path=PROJECT_ROOT / ".env",
            )
        except Exception as exc:  # noqa: BLE001 - normalize voice adapter failures for the UI.
            self._send_json({"error": f"Speech synthesis failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"speech": speech_to_api(speech)})

    def _handle_train_voice(self, path: str) -> None:
        clone_id = _clone_id_from_path(path.removesuffix("/voice/train"))
        store = self._store()
        try:
            profile = store.load_clone(clone_id)
        except FileNotFoundError:
            self._send_json({"error": "Clone not found"}, HTTPStatus.NOT_FOUND)
            return

        try:
            status = train_voice_model(
                profile=profile,
                sample_paths=_voice_sample_paths(profile),
                env_path=PROJECT_ROOT / ".env",
            )
            store.update_voice_status(clone_id, status)
            profile.voice = status
        except Exception as exc:  # noqa: BLE001 - normalize voice adapter failures for the UI.
            self._send_json({"error": f"Voice training failed: {exc}"}, HTTPStatus.BAD_GATEWAY)
            return
        self._send_json({"voice": asdict(status), "clone": profile_to_api(profile)})

    def _serve_static(self, path: str) -> None:
        relative = "index.html" if path in ("", "/") else path.lstrip("/")
        requested = (WEB_ROOT / relative).resolve()
        if not _is_relative_to(requested, WEB_ROOT.resolve()) or not requested.is_file():
            self._send_json({"error": "Not found"}, HTTPStatus.NOT_FOUND)
            return

        content_type = mimetypes.guess_type(requested.name)[0] or "application/octet-stream"
        body = requested.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, object]:
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

    def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _store(self) -> CloneStore:
        return CloneStore(DATA_ROOT)


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    server = ThreadingHTTPServer((host, port), CloneRequestHandler)
    try:
        print(f"Cyber Clone MVP running at http://{host}:{port}", flush=True)
    except OSError:
        pass
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Cyber Clone MVP web server.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    run(args.host, args.port)


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


def _clone_id_from_path(path: str) -> str:
    parts = _path_parts(path)
    if len(parts) < 3:
        raise ValueError("Clone id is required")
    return parts[2]


def _path_parts(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def _first_voice_sample_path(profile: CloneProfile) -> Path | None:
    sample_paths = _voice_sample_paths(profile)
    return sample_paths[0] if sample_paths else None


def _voice_sample_paths(profile: CloneProfile) -> list[Path]:
    if not profile.voice:
        return []

    filenames = list(profile.voice.sample_filenames)
    if profile.voice.sample_filename:
        filenames.insert(0, profile.voice.sample_filename)

    sample_paths = []
    seen = set()
    for filename in filenames:
        sample_path = DATA_ROOT / profile.clone_id / "voice" / Path(filename).name
        if sample_path.is_file() and sample_path not in seen:
            sample_paths.append(sample_path)
            seen.add(sample_path)
    return sample_paths


def speech_to_api(speech: SpeechSynthesisResult) -> dict[str, object]:
    return {
        "status": speech.status,
        "backend": speech.backend,
        "message": speech.message,
        "audioDataUrl": speech.audio_data_url,
        "contentType": speech.content_type,
        "emotion": speech.emotion,
    }


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


if __name__ == "__main__":
    main()
