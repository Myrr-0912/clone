from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Protocol
from urllib import error, request


ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "src"
SAMPLE_WAV_DATA_URL = "data:audio/wav;base64,UklGRg=="


class SmokeError(RuntimeError):
    pass


class JsonClient(Protocol):
    def get_json(self, path: str) -> dict[str, object]:
        ...

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        ...


class SmokeClient:
    def __init__(self, base_url: str, timeout_seconds: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.opener = request.build_opener(request.ProxyHandler({}))

    def get_json(self, path: str) -> dict[str, object]:
        return self._request_json("GET", path)

    def post_json(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        return self._request_json("POST", path, payload)

    def _request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method=method,
        )
        try:
            with self.opener.open(req, timeout=self.timeout_seconds) as response:
                decoded = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise SmokeError(f"{method} {path} failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise SmokeError(f"{method} {path} failed: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SmokeError(f"{method} {path} did not return JSON") from exc

        if not isinstance(decoded, dict):
            raise SmokeError(f"{method} {path} response must be a JSON object")
        return decoded


def run_smoke(client: JsonClient) -> dict[str, object]:
    health = client.get_json("/api/health")
    if health.get("ok") is not True:
        raise SmokeError("/api/health did not return ok=true")

    created = client.post_json(
        "/api/clones",
        {
            "targetName": "Smoke Target",
            "chatText": "Smoke Target: hello\nUser: say something short",
            "voiceFiles": [{"name": "smoke-sample.wav", "data": SAMPLE_WAV_DATA_URL}],
        },
    )
    clone_id = _required_nested_string(created, "clone", "cloneId")

    appended = client.post_json(
        f"/api/clones/{clone_id}/voice/samples",
        {"voiceFiles": [{"name": "smoke-extra.wav", "data": SAMPLE_WAV_DATA_URL}]},
    )
    sample_count = _required_nested_int(appended, "voice", "sample_count")
    if sample_count < 2:
        raise SmokeError(f"voice/samples returned sample_count={sample_count}, expected at least 2")

    trained = client.post_json(f"/api/clones/{clone_id}/voice/train", {})
    voice_status = _required_nested_string(trained, "voice", "status")
    if voice_status != "ready":
        raise SmokeError(f"voice/train returned status={voice_status!r}, expected 'ready'")

    refreshed = client.get_json(f"/api/clones/{clone_id}/voice/status")
    refreshed_status = _required_nested_string(refreshed, "voice", "status")
    if refreshed_status != voice_status:
        raise SmokeError(
            f"voice/status returned status={refreshed_status!r}, expected {voice_status!r}"
        )

    chatted = client.post_json(
        f"/api/clones/{clone_id}/chat",
        {"message": "say something in your usual style"},
    )
    reply = _required_nested_string(chatted, "reply", "text")
    emotion = _optional_nested_string(chatted, "reply", "emotion") or "warm"

    spoken = client.post_json(f"/api/clones/{clone_id}/speak", {"text": reply, "emotion": emotion})
    speech = _required_mapping(spoken, "speech")
    backend = _required_string(speech, "backend")
    audio_data_url = _required_string(speech, "audioDataUrl")
    if not audio_data_url.startswith("data:audio/wav;base64,"):
        raise SmokeError("speech.audioDataUrl must be a WAV data URL")

    return {
        "cloneId": clone_id,
        "voiceStatus": voice_status,
        "voiceSampleCount": sample_count,
        "replyText": reply,
        "speechBackend": backend,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local mock API smoke flow.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    parser.add_argument(
        "--start-server",
        action="store_true",
        help="Launch cyberclone.web with local/mock backends for this smoke run.",
    )
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    process: subprocess.Popen[str] | None = None
    try:
        if args.start_server:
            process = _start_server(args.host, args.port)
            _wait_for_server(base_url, args.timeout_seconds)

        summary = run_smoke(SmokeClient(base_url, timeout_seconds=args.timeout_seconds))
    except SmokeError as exc:
        print(f"SMOKE FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
    finally:
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)

    print("SMOKE PASS")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def _start_server(host: str, port: int) -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = _prepend_path(str(SRC_ROOT), env.get("PYTHONPATH", ""))
    env["NO_PROXY"] = _prepend_csv("127.0.0.1,localhost,::1", env.get("NO_PROXY", ""))
    env["no_proxy"] = _prepend_csv("127.0.0.1,localhost,::1", env.get("no_proxy", ""))
    env["LLM_BACKEND"] = "local"
    env["VOICE_TRAINING_BACKEND"] = "mock"
    env["VOICE_TTS_BACKEND"] = "mock"
    return subprocess.Popen(
        [sys.executable, "-m", "cyberclone.web", "--host", host, "--port", str(port)],
        cwd=str(ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _wait_for_server(base_url: str, timeout_seconds: float) -> None:
    client = SmokeClient(base_url, timeout_seconds=1.0)
    deadline = time.monotonic() + timeout_seconds
    last_error = "server did not respond"
    while time.monotonic() < deadline:
        try:
            if client.get_json("/api/health").get("ok") is True:
                return
        except SmokeError as exc:
            last_error = str(exc)
        time.sleep(0.1)
    raise SmokeError(f"server failed to become healthy: {last_error}")


def _required_nested_string(payload: dict[str, object], section: str, key: str) -> str:
    return _required_string(_required_mapping(payload, section), key)


def _required_nested_int(payload: dict[str, object], section: str, key: str) -> int:
    value = _required_mapping(payload, section).get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SmokeError(f"response missing integer: {section}.{key}")
    return value


def _optional_nested_string(payload: dict[str, object], section: str, key: str) -> str:
    value = _required_mapping(payload, section).get(key)
    return value.strip() if isinstance(value, str) else ""


def _required_mapping(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise SmokeError(f"response missing object: {key}")
    return value


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SmokeError(f"response missing string: {key}")
    return value.strip()


def _prepend_path(value: str, existing: str) -> str:
    return value if not existing else f"{value}{os.pathsep}{existing}"


def _prepend_csv(value: str, existing: str) -> str:
    return value if not existing else f"{value},{existing}"


if __name__ == "__main__":
    main()
