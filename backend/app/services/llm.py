from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Callable, Mapping, MutableMapping, Protocol
from urllib import error, request

from app.models.clone import ChatReply, CloneProfile
from app.services.chat_engine import LocalCloneChatEngine, infer_emotion
from app.services.persona import profile_to_system_prompt


class ChatEngine(Protocol):
    def reply(self, profile: CloneProfile, user_text: str, retrieved_context: str = "") -> ChatReply:
        ...


Transport = Callable[[str, dict[str, str], dict[str, object], float], dict[str, object]]


@dataclass(slots=True)
class LLMSettings:
    api_key: str = ""
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-v4-flash"
    timeout_seconds: float = 30.0
    temperature: float = 0.7
    max_tokens: int = 800

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "LLMSettings":
        source = env or os.environ
        return cls(
            api_key=_get_first(source, "DEEPSEEK_API_KEY", "LLM_API_KEY"),
            base_url=source.get("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/"),
            model=source.get("LLM_MODEL", "deepseek-v4-flash"),
            timeout_seconds=_float_env(source.get("LLM_TIMEOUT_SECONDS"), 30.0),
            temperature=_float_env(source.get("LLM_TEMPERATURE"), 0.7),
            max_tokens=_int_env(source.get("LLM_MAX_TOKENS"), 800),
        )


class DeepSeekChatEngine:
    def __init__(
        self,
        settings: LLMSettings,
        transport: Transport | None = None,
    ) -> None:
        self.settings = settings
        self.transport = transport or _post_json

    def reply(self, profile: CloneProfile, user_text: str, retrieved_context: str = "") -> ChatReply:
        system_prompt = _profile_prompt(profile)
        if retrieved_context.strip():
            system_prompt = f"{system_prompt}\n\n{retrieved_context.strip()}"
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_text},
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self.settings.max_tokens,
            "stream": False,
        }
        response = self.transport(
            f"{self.settings.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            self.settings.timeout_seconds,
        )
        return ChatReply(
            clone_id=profile.clone_id,
            text=_extract_message(response),
            emotion=infer_emotion(user_text),
        )


def create_chat_engine(
    env_path: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> ChatEngine:
    source = dict(os.environ if env is None else env)
    if env_path is not None:
        load_env_file(env_path, source)

    if source.get("LLM_BACKEND", "").strip().lower() == "local":
        return LocalCloneChatEngine()

    settings = LLMSettings.from_env(source)
    if settings.enabled:
        return DeepSeekChatEngine(settings)
    return LocalCloneChatEngine()


def load_env_file(path: Path, env: MutableMapping[str, str] | None = None) -> None:
    target = env if env is not None else os.environ
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in target:
            continue
        target[key] = _strip_quotes(value.strip())


def _profile_prompt(profile: CloneProfile) -> str:
    return profile_to_system_prompt(profile)


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API request failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM API request failed: {exc.reason}") from exc


def _extract_message(response: dict[str, object]) -> str:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or not choices:
            raise KeyError("choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise KeyError("choices[0]")
        message = first["message"]
        if not isinstance(message, dict):
            raise KeyError("message")
        content = message["content"]
    except KeyError as exc:
        raise RuntimeError("LLM API response did not include a chat message") from exc

    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM API response message was empty")
    return content.strip()


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _get_first(source: Mapping[str, str], *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value:
            return value
    return ""


def _float_env(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default
