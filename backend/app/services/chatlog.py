from __future__ import annotations

import json
import re
from typing import Any

from app.models.clone import ChatMessage

_LINE_RE = re.compile(
    r"^(?:(?P<timestamp>\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(?::\d{2})?)\s+)?"
    r"(?P<speaker>[^:：]{1,64})[:：]\s*(?P<text>.+)$"
)


def parse_chat_log(raw: str, target_name: str) -> list[ChatMessage]:
    """Parse common exported chat formats into normalized messages."""
    text = raw.strip()
    if not text:
        return []

    json_messages = _try_parse_json(text, target_name)
    if json_messages is not None:
        return json_messages

    return _parse_lines(text, target_name)


def _try_parse_json(raw: str, target_name: str) -> list[ChatMessage] | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None

    if isinstance(data, dict):
        for key in ("messages", "chat", "records"):
            if isinstance(data.get(key), list):
                data = data[key]
                break

    if not isinstance(data, list):
        return None

    messages: list[ChatMessage] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        speaker = _first_string(item, "sender", "speaker", "name", "from", "author")
        content = _first_string(item, "content", "text", "message", "body")
        if not speaker or not content:
            continue
        timestamp = _first_string(item, "timestamp", "time", "created_at", "date")
        messages.append(
            ChatMessage(
                speaker=speaker.strip(),
                text=content.strip(),
                is_target=_same_name(speaker, target_name),
                timestamp=timestamp.strip() if timestamp else None,
            )
        )
    return messages


def _parse_lines(raw: str, target_name: str) -> list[ChatMessage]:
    messages: list[ChatMessage] = []
    continuation: list[str] = []

    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        match = _LINE_RE.match(stripped)
        if match:
            if continuation and messages:
                messages[-1].text = f"{messages[-1].text}\n" + "\n".join(continuation)
                continuation.clear()

            speaker = match.group("speaker").strip()
            messages.append(
                ChatMessage(
                    speaker=speaker,
                    text=match.group("text").strip(),
                    is_target=_same_name(speaker, target_name),
                    timestamp=match.group("timestamp"),
                )
            )
        elif messages:
            continuation.append(stripped)

    if continuation and messages:
        messages[-1].text = f"{messages[-1].text}\n" + "\n".join(continuation)

    return messages


def _first_string(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _same_name(left: str, right: str) -> bool:
    return left.strip().casefold() == right.strip().casefold()
