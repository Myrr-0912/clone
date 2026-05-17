import hashlib
import json
import math
import sqlite3


DEFAULT_DIMENSIONS = 128
MIN_ITEMS_PER_CHUNK = 3
MAX_ITEMS_PER_CHUNK = 6
MAX_CHARS_PER_CHUNK = 1200


def build_hash_embedding(text, dimensions=DEFAULT_DIMENSIONS):
    """Build a deterministic local embedding that can be swapped later."""
    dimensions = int(dimensions)
    if dimensions <= 0:
        raise ValueError("dimensions must be greater than zero")

    vector = [0.0] * dimensions
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] & 1 else -1.0
        vector[index] += sign

    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude == 0.0:
        return vector
    return [value / magnitude for value in vector]


def cosine_similarity(left, right):
    if len(left) != len(right):
        raise ValueError("embedding dimensions must match")
    if not left:
        return 0.0

    dot = 0.0
    left_norm = 0.0
    right_norm = 0.0
    for left_value, right_value in zip(left, right):
        dot += left_value * right_value
        left_norm += left_value * left_value
        right_norm += right_value * right_value

    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (math.sqrt(left_norm) * math.sqrt(right_norm))


def create_or_replace_index(db_path, user_id, clone_id, chunks):
    normalized_chunks = _chunk_items(chunks)

    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        connection.execute(
            "DELETE FROM chunks WHERE user_id = ? AND clone_id = ?",
            (str(user_id), str(clone_id)),
        )
        for ordinal, chunk in enumerate(normalized_chunks):
            chunk_id = _chunk_id(user_id, clone_id, ordinal, chunk["text"])
            embedding = build_hash_embedding(chunk["text"])
            connection.execute(
                """
                INSERT INTO chunks (
                    user_id,
                    clone_id,
                    chunk_id,
                    text,
                    metadata_json,
                    embedding_json
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    str(user_id),
                    str(clone_id),
                    chunk_id,
                    chunk["text"],
                    json.dumps(chunk["metadata"], ensure_ascii=False, sort_keys=True),
                    json.dumps(embedding, separators=(",", ":")),
                ),
            )
        connection.commit()
    finally:
        connection.close()


def index_chunks(db_path, chunks):
    normalized = list(chunks or [])
    if not normalized:
        return create_or_replace_index(db_path, "", "", [])
    metadata = normalized[0].get("metadata", {}) if isinstance(normalized[0], dict) else {}
    user_id = metadata.get("user_id") or metadata.get("userId")
    clone_id = metadata.get("clone_id") or metadata.get("cloneId")
    if not user_id or not clone_id:
        raise ValueError("chunk metadata must include user_id and clone_id")
    create_or_replace_index(db_path, user_id, clone_id, normalized)
    return {"indexed": len(normalized)}


def search(db_path, user_id, clone_id, query, top_k):
    query = str(query).strip()
    top_k = int(top_k)
    if not query or top_k <= 0:
        return []

    query_tokens = set(_tokenize(query))
    query_embedding = build_hash_embedding(query)
    scored = []

    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        rows = connection.execute(
            """
            SELECT chunk_id, text, metadata_json, embedding_json, created_at
            FROM chunks
            WHERE user_id = ? AND clone_id = ?
            """,
            (str(user_id), str(clone_id)),
        ).fetchall()
    finally:
        connection.close()

    for chunk_id, text, metadata_json, embedding_json, created_at in rows:
        if query_tokens and not query_tokens.intersection(_tokenize(text)):
            continue
        try:
            embedding = json.loads(embedding_json)
        except json.JSONDecodeError:
            continue
        score = cosine_similarity(query_embedding, embedding)
        if score <= 0.0:
            continue
        try:
            metadata = json.loads(metadata_json)
        except json.JSONDecodeError:
            metadata = {}
        scored.append(
            {
                "chunk_id": chunk_id,
                "text": text,
                "metadata": metadata,
                "score": score,
                "created_at": created_at,
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["chunk_id"]))
    return scored[:top_k]


def search_chunks(db_path, *, user_id, clone_id, query, top_k):
    return search(db_path, user_id, clone_id, query, top_k)


def stats(db_path):
    connection = sqlite3.connect(db_path)
    try:
        _ensure_schema(connection)
        chunk_count, updated_at = connection.execute(
            "SELECT COUNT(*), MAX(created_at) FROM chunks"
        ).fetchone()
        page_count = connection.execute("PRAGMA page_count").fetchone()[0]
        page_size = connection.execute("PRAGMA page_size").fetchone()[0]
        connection.commit()
    finally:
        connection.close()

    return {
        "chunk_count": int(chunk_count),
        "db_size_bytes": int(page_count) * int(page_size),
        "updated_at": updated_at,
    }


def _ensure_schema(connection):
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            user_id TEXT NOT NULL,
            clone_id TEXT NOT NULL,
            chunk_id TEXT NOT NULL,
            text TEXT NOT NULL,
            metadata_json TEXT NOT NULL,
            embedding_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (
                strftime('%Y-%m-%dT%H:%M:%fZ', 'now')
            ),
            PRIMARY KEY (user_id, clone_id, chunk_id)
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_chunks_user_clone
        ON chunks (user_id, clone_id)
        """
    )


def _chunk_items(items):
    normalized = [
        item
        for item in (_normalize_item(raw_item, ordinal) for ordinal, raw_item in enumerate(items or []))
        if item["text"]
    ]
    chunks = []
    index = 0
    while index < len(normalized):
        limit = _next_chunk_limit(len(normalized) - index)
        current = []
        current_length = 0
        while index < len(normalized) and len(current) < limit:
            candidate = normalized[index]
            candidate_length = len(candidate["text"])
            would_exceed = current and current_length + candidate_length + 1 > MAX_CHARS_PER_CHUNK
            if would_exceed:
                break
            current.append(candidate)
            current_length += candidate_length + (1 if current_length else 0)
            index += 1

        if not current:
            current.append(normalized[index])
            index += 1

        text = "\n".join(item["text"] for item in current)
        metadata = {
            "source_count": len(current),
            "source_ordinals": [item["metadata"]["ordinal"] for item in current],
            "items": [item["metadata"] for item in current],
            "char_count": len(text),
        }
        chunks.append({"text": text, "metadata": metadata})
    return chunks


def _next_chunk_limit(remaining):
    limit = min(MAX_ITEMS_PER_CHUNK, remaining)
    while remaining - limit in (1, 2) and limit > MIN_ITEMS_PER_CHUNK:
        limit -= 1
    return limit


def _normalize_item(item, ordinal):
    if isinstance(item, str):
        text = item.strip()
        metadata = {"ordinal": ordinal, "source_type": "text"}
    elif isinstance(item, dict):
        text = _first_text_value(item, "text", "content", "message", "body")
        metadata = _metadata_from_mapping(item, ordinal)
    else:
        raw_text = getattr(item, "text", "")
        text = str(raw_text).strip()
        metadata = _metadata_from_object(item, ordinal)

    return {"text": text, "metadata": metadata}


def _first_text_value(item, *keys):
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _metadata_from_mapping(item, ordinal):
    raw_metadata = item.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    metadata.setdefault("ordinal", ordinal)
    metadata.setdefault("source_type", "mapping")
    for key in ("speaker", "sender", "author", "timestamp", "time", "created_at"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            metadata[key] = value.strip()
    if "is_target" in item:
        metadata["is_target"] = bool(item["is_target"])
    return metadata


def _metadata_from_object(item, ordinal):
    metadata = {"ordinal": ordinal, "source_type": "message"}
    for key in ("speaker", "timestamp"):
        value = getattr(item, key, None)
        if isinstance(value, str) and value.strip():
            metadata[key] = value.strip()
    if hasattr(item, "is_target"):
        metadata["is_target"] = bool(getattr(item, "is_target"))
    return metadata


def _chunk_id(user_id, clone_id, ordinal, text):
    digest = hashlib.sha256(
        f"{user_id}\0{clone_id}\0{ordinal}\0{text}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{ordinal:06d}-{digest}"


def _tokenize(text):
    tokens = []
    word = []
    cjk = []

    for character in str(text).casefold():
        if _is_cjk(character):
            _flush_word(tokens, word)
            cjk.append(character)
        elif character.isalnum() or character in "_+-":
            _flush_cjk(tokens, cjk)
            word.append(character)
        else:
            _flush_word(tokens, word)
            _flush_cjk(tokens, cjk)

    _flush_word(tokens, word)
    _flush_cjk(tokens, cjk)
    return tokens


def _flush_word(tokens, word):
    if not word:
        return
    token = "".join(word)
    tokens.append(token)
    if len(token) >= 6:
        for index in range(0, len(token) - 3):
            tokens.append(token[index : index + 4])
    word.clear()


def _flush_cjk(tokens, cjk):
    if not cjk:
        return
    tokens.extend(cjk)
    text = "".join(cjk)
    for size in (2, 3, 4):
        if len(text) < size:
            continue
        for index in range(0, len(text) - size + 1):
            tokens.append(text[index : index + size])
    cjk.clear()


def _is_cjk(character):
    return "\u4e00" <= character <= "\u9fff"
