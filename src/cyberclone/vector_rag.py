from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Iterable


@dataclass(frozen=True, slots=True)
class _MessageWindowItem:
    ordinal: int
    speaker: str
    text: str
    is_target: bool
    timestamp: str | None


def build_chunks_from_messages(
    messages: list[Any],
    user_id: str,
    clone_id: str,
    target_name: str,
) -> list[dict[str, Any]]:
    normalized = _normalize_messages(messages, target_name)
    chunks: list[dict[str, Any]] = []

    for compact_index, primary in enumerate(normalized):
        start = max(0, compact_index - 1)
        end = min(len(normalized), compact_index + 2)
        window = normalized[start:end]
        metadata = {
            "user_id": user_id,
            "clone_id": clone_id,
            "target_name": target_name,
            "primary_ordinal": primary.ordinal,
            "primary_speaker": primary.speaker,
            "speakers": [item.speaker for item in window],
            "ordinals": [item.ordinal for item in window],
            "contains_target": any(item.is_target for item in window),
            "timestamps": [item.timestamp for item in window],
        }
        chunks.append(
            {
                "id": _chunk_id(user_id, clone_id, primary.ordinal),
                "text": _format_chunk_text(window, primary.ordinal),
                "metadata": metadata,
            }
        )

    return chunks


def format_vector_evidence(results: Iterable[Any]) -> str:
    lines = [
        "## Retrieved Vector Evidence",
        "Use only the retrieved chunks below as evidence. Do not invent facts, messages, memories, or private experiences that are not supported here.",
    ]
    result_lines = []

    for index, result in enumerate(results, start=1):
        text = _result_text(result)
        if not text:
            continue
        metadata = _result_metadata(result)
        parts = [f"chunk {index}"]
        ordinals = _format_ordinals(metadata.get("ordinals"))
        if ordinals:
            parts.append(ordinals)
        speakers = _format_speakers(metadata.get("speakers"))
        if speakers:
            parts.append(f"speakers {speakers}")
        if metadata.get("contains_target") is True:
            parts.append("contains target")
        score = _result_score(result)
        if score is not None:
            parts.append(f"score {score:.3g}")
        result_lines.append(f"- [{' | '.join(parts)}] {text}")

    if not result_lines:
        return ""
    return "\n".join([*lines, *result_lines])


def index_clone_messages(
    db_path: str,
    user_id: str,
    clone_id: str,
    messages: list[Any],
    target_name: str,
) -> Any:
    chunks = build_chunks_from_messages(messages, user_id, clone_id, target_name)
    vector_store = _load_vector_store()
    return _index_chunks(vector_store, db_path, chunks)


def retrieve_clone_evidence(
    db_path: str,
    user_id: str,
    clone_id: str,
    query: str,
    top_k: int = 8,
) -> str:
    if top_k <= 0 or not query.strip():
        return ""
    vector_store = _load_vector_store()
    results = _search_chunks(
        vector_store,
        db_path,
        user_id=user_id,
        clone_id=clone_id,
        query=query,
        top_k=top_k,
    )
    return format_vector_evidence(results)


def _normalize_messages(messages: list[Any], target_name: str) -> list[_MessageWindowItem]:
    normalized: list[_MessageWindowItem] = []
    for ordinal, message in enumerate(messages):
        text = _message_value(message, "text").strip()
        if not text:
            continue
        speaker = _message_value(message, "speaker").strip()
        timestamp = _optional_message_value(message, "timestamp")
        is_target = _message_is_target(message, speaker, target_name)
        normalized.append(
            _MessageWindowItem(
                ordinal=ordinal,
                speaker=speaker,
                text=text,
                is_target=is_target,
                timestamp=timestamp,
            )
        )
    return normalized


def _format_chunk_text(window: list[_MessageWindowItem], primary_ordinal: int) -> str:
    lines = [f"Conversation chunk centered on ordinal {primary_ordinal}."]
    for item in window:
        role = "TARGET" if item.is_target else "OTHER"
        timestamp = f" [{item.timestamp}]" if item.timestamp else ""
        text = item.text.replace("\r", " ").replace("\n", " / ").strip()
        lines.append(f"{item.ordinal}. {role} {item.speaker}{timestamp}: {text}")
    return "\n".join(lines)


def _message_value(message: Any, key: str) -> str:
    if isinstance(message, dict):
        return str(message.get(key, ""))
    return str(getattr(message, key, ""))


def _optional_message_value(message: Any, key: str) -> str | None:
    value = message.get(key) if isinstance(message, dict) else getattr(message, key, None)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _message_is_target(message: Any, speaker: str, target_name: str) -> bool:
    if isinstance(message, dict) and "is_target" in message:
        return bool(message.get("is_target"))
    if not isinstance(message, dict) and hasattr(message, "is_target"):
        return bool(getattr(message, "is_target"))
    return bool(target_name.strip()) and speaker.casefold() == target_name.strip().casefold()


def _chunk_id(user_id: str, clone_id: str, ordinal: int) -> str:
    return f"{_safe_id(user_id)}:{_safe_id(clone_id)}:chat:{ordinal:06d}"


def _safe_id(value: str) -> str:
    text = str(value).strip()
    return text.replace(":", "_").replace(" ", "_") or "unknown"


def _load_vector_store() -> Any:
    return import_module(".vector_store", __package__)


def _index_chunks(vector_store: Any, db_path: str, chunks: list[dict[str, Any]]) -> Any:
    if hasattr(vector_store, "index_chunks"):
        return vector_store.index_chunks(db_path, chunks)
    if hasattr(vector_store, "upsert_chunks"):
        return vector_store.upsert_chunks(db_path, chunks)
    store = _vector_store_instance(vector_store, db_path)
    for method_name in ("index_chunks", "upsert_chunks", "add_chunks"):
        method = getattr(store, method_name, None)
        if method:
            return method(chunks)
    raise AttributeError("vector_store must expose index_chunks(db_path, chunks)")


def _search_chunks(
    vector_store: Any,
    db_path: str,
    *,
    user_id: str,
    clone_id: str,
    query: str,
    top_k: int,
) -> Any:
    for function_name in ("search_chunks", "search"):
        function = getattr(vector_store, function_name, None)
        if function:
            return function(
                db_path,
                user_id=user_id,
                clone_id=clone_id,
                query=query,
                top_k=top_k,
            )

    store = _vector_store_instance(vector_store, db_path)
    for method_name in ("search_chunks", "search"):
        method = getattr(store, method_name, None)
        if method:
            return method(user_id=user_id, clone_id=clone_id, query=query, top_k=top_k)
    raise AttributeError("vector_store must expose search_chunks(db_path, user_id, clone_id, query, top_k)")


def _vector_store_instance(vector_store: Any, db_path: str) -> Any:
    store_class = getattr(vector_store, "VectorStore", None)
    if store_class is None:
        raise AttributeError("vector_store must expose index/search functions or a VectorStore class")
    return store_class(db_path)


def _result_text(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("text") or result.get("content") or result.get("chunk")
    else:
        value = getattr(result, "text", None) or getattr(result, "content", None) or getattr(result, "chunk", None)
    return str(value).replace("\r", " ").replace("\n", " / ").strip() if value is not None else ""


def _result_metadata(result: Any) -> dict[str, Any]:
    if isinstance(result, dict):
        value = result.get("metadata", {})
    else:
        value = getattr(result, "metadata", {})
    return value if isinstance(value, dict) else {}


def _result_score(result: Any) -> float | None:
    if isinstance(result, dict):
        value = result.get("score")
    else:
        value = getattr(result, "score", None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_ordinals(value: Any) -> str:
    if isinstance(value, list) and value:
        ordinals = [str(item) for item in value]
    elif value is not None:
        ordinals = [str(value)]
    else:
        return ""
    label = "ordinal" if len(ordinals) == 1 else "ordinals"
    return f"{label} {', '.join(ordinals)}"


def _format_speakers(value: Any) -> str:
    if isinstance(value, list):
        speakers = [str(item).strip() for item in value if str(item).strip()]
        return ", ".join(speakers)
    if value is None:
        return ""
    return str(value).strip()
