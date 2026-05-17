from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any, Callable
from urllib.parse import urlencode, urljoin, quote
from urllib.request import ProxyHandler, Request, build_opener


RequestJson = Callable[[str, dict[str, str], dict[str, str]], dict[str, Any]]


@dataclass(slots=True)
class WeFlowSession:
    session_id: str
    name: str
    platform: str
    session_type: str
    message_count: int | None = None
    last_message_at: int | None = None


class WeFlowClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:5031",
        token: str = "",
        request_json: RequestJson | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token.strip()
        self._request_json = request_json or self._urllib_request_json

    def health(self) -> bool:
        try:
            payload = self._request_json("/health", {}, {})
        except OSError:
            return False
        return payload.get("status") == "ok"

    def list_sessions(self, keyword: str = "", limit: int = 100) -> list[WeFlowSession]:
        params = {"format": "chatlab", "limit": str(limit)}
        if keyword.strip():
            params["keyword"] = keyword.strip()
        payload = self._request_json("/api/v1/sessions", params, self._headers())
        return [
            WeFlowSession(
                session_id=str(item.get("id", "")),
                name=str(item.get("name", "")),
                platform=str(item.get("platform", "wechat")),
                session_type=str(item.get("type", "private")),
                message_count=_optional_int(item.get("messageCount")),
                last_message_at=_optional_int(item.get("lastMessageAt")),
            )
            for item in payload.get("sessions", [])
            if isinstance(item, dict) and item.get("id")
        ]

    def pull_session_training_text(self, session_id: str, limit: int = 5000, offset: int = 0) -> str:
        safe_session_id = quote(session_id, safe="")
        payload = self._request_json(
            f"/api/v1/sessions/{safe_session_id}/messages",
            {"limit": str(limit), "offset": str(offset)},
            self._headers(),
        )
        return chatlab_to_training_text(payload)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _urllib_request_json(
        self,
        path: str,
        params: dict[str, str],
        headers: dict[str, str],
    ) -> dict[str, Any]:
        query = f"?{urlencode(params)}" if params else ""
        url = urljoin(f"{self.base_url}/", path.lstrip("/")) + query
        request = Request(url, headers=headers)
        opener = build_opener(ProxyHandler({}))
        with opener.open(request, timeout=10) as response:
            body = response.read().decode("utf-8")
        payload = json.loads(body)
        if not isinstance(payload, dict):
            raise ValueError("WeFlow response must be a JSON object")
        return payload


def chatlab_to_training_text(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    for item in payload.get("messages", []):
        if not isinstance(item, dict):
            continue
        content = _message_content(item)
        if not content:
            continue
        speaker = _message_speaker(item)
        timestamp = _format_timestamp(item.get("timestamp"))
        prefix = f"{timestamp} " if timestamp else ""
        lines.append(f"{prefix}{speaker}: {content}")
    return "\n".join(lines)


def _message_speaker(item: dict[str, Any]) -> str:
    for key in ("groupNickname", "accountName", "sender"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return "Unknown"


def _message_content(item: dict[str, Any]) -> str:
    value = item.get("content")
    if isinstance(value, str) and value.strip():
        return value.strip().replace("\r\n", "\n").replace("\r", "\n")
    return ""


def _format_timestamp(value: Any) -> str:
    timestamp = _optional_int(value)
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d %H:%M")


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.isdigit():
        return int(value)
    return None
