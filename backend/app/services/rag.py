from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import re
from typing import Any

from app.services.chatlog import ChatMessage

_ASCII_TOKEN_RE = re.compile(r"[A-Za-z0-9_+-]{2,}")
_CJK_RE = re.compile(r"[\u4e00-\u9fff]+")


@dataclass(slots=True)
class ChatRecord:
    speaker: str
    text: str
    is_target: bool
    timestamp: str | None = None
    ordinal: int = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChatRecord":
        return cls(
            speaker=str(data.get("speaker", "")).strip(),
            text=str(data.get("text", "")).strip(),
            is_target=bool(data.get("is_target")),
            timestamp=str(data["timestamp"]).strip() if data.get("timestamp") else None,
            ordinal=_int_value(data.get("ordinal"), 0),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class RetrievedSnippet:
    speaker: str
    text: str
    is_target: bool
    timestamp: str | None
    ordinal: int
    score: float


def build_chat_index(messages: list[ChatMessage]) -> list[ChatRecord]:
    return [
        ChatRecord(
            speaker=message.speaker,
            text=message.text,
            is_target=message.is_target,
            timestamp=message.timestamp,
            ordinal=index,
        )
        for index, message in enumerate(messages)
        if message.text.strip()
    ]


def chat_index_to_jsonable(records: list[ChatRecord]) -> list[dict[str, Any]]:
    return [record.to_dict() for record in records]


def chat_index_from_jsonable(value: Any) -> list[ChatRecord]:
    if not isinstance(value, list):
        return []
    records = []
    for item in value:
        if isinstance(item, dict):
            record = ChatRecord.from_dict(item)
            if record.text:
                records.append(record)
    return records


def retrieve_relevant_messages(
    records: list[ChatRecord],
    query: str,
    max_snippets: int = 8,
) -> list[RetrievedSnippet]:
    query = query.strip()
    if not query or not records or max_snippets <= 0:
        return []

    query_terms = _terms(query)
    scored = []
    for record in records:
        score = _score_record(record, query, query_terms)
        if score > 0:
            scored.append((score, record))

    scored.sort(key=lambda item: (-item[0], item[1].ordinal))
    selected_ordinals: set[int] = set()
    selected: list[RetrievedSnippet] = []
    for score, record in scored:
        for candidate in _window(records, record.ordinal):
            if candidate.ordinal in selected_ordinals:
                continue
            selected.append(
                RetrievedSnippet(
                    speaker=candidate.speaker,
                    text=candidate.text,
                    is_target=candidate.is_target,
                    timestamp=candidate.timestamp,
                    ordinal=candidate.ordinal,
                    score=score if candidate.ordinal == record.ordinal else score * 0.45,
                )
            )
            selected_ordinals.add(candidate.ordinal)
            if len(selected) >= max_snippets:
                return selected

    return selected


def format_retrieved_context(snippets: list[RetrievedSnippet]) -> str:
    if not snippets:
        return ""

    lines = [
        "## Retrieved Chat Evidence",
        "以下是真实聊天记录中与用户当前消息最相关的片段。优先参考这些片段的事实、称呼、语气和表达节奏；不要编造片段之外的私人经历。",
    ]
    for snippet in snippets:
        role = "TARGET" if snippet.is_target else "OTHER"
        timestamp = snippet.timestamp or "no-time"
        text = snippet.text.replace("\r", " ").replace("\n", " / ").strip()
        lines.append(f"- [{timestamp}] {role} {snippet.speaker}: {text}")
    return "\n".join(lines)


def _score_record(record: ChatRecord, query: str, query_terms: Counter[str]) -> float:
    text = record.text.strip()
    terms = _terms(text)
    overlap = sum(min(query_terms[term], terms.get(term, 0)) for term in query_terms)
    if not overlap:
        return 0.0

    score = float(overlap)
    if query in text or text in query:
        score += 8.0
    if record.is_target:
        score *= 1.2
    score += min(len(text), 80) / 400.0
    return score


def _terms(text: str) -> Counter[str]:
    normalized = text.casefold()
    terms: Counter[str] = Counter(_ASCII_TOKEN_RE.findall(normalized))
    for block in _CJK_RE.findall(normalized):
        if len(block) == 1:
            terms[block] += 1
            continue
        for size in (2, 3, 4):
            if len(block) < size:
                continue
            for index in range(0, len(block) - size + 1):
                terms[block[index : index + size]] += 1
    return terms


def _window(records: list[ChatRecord], ordinal: int) -> list[ChatRecord]:
    lookup = {record.ordinal: record for record in records}
    return [lookup[index] for index in (ordinal, ordinal + 1, ordinal - 1) if index in lookup]


def _int_value(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
