from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

_VECTOR_DIR_NAMES = ("vector", "vector_db", "vectors")
_VECTOR_MANIFEST_NAMES = ("manifest.json", "vector_manifest.json")
_VECTOR_DB_DIR_NAMES = ("db", "index", "chroma", "faiss")
_AUDIO_EXTENSIONS = {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".opus", ".wav", ".webm"}
_MODEL_DIR_NAMES = {"adapter", "adapters", "checkpoint", "checkpoints", "model", "models"}
_MODEL_FILE_EXTENSIONS = {".bin", ".ckpt", ".index", ".onnx", ".pt", ".pth", ".safetensors"}


def list_clone_resource_stats(users_root: str | Path = Path("data/users")) -> list[dict[str, object]]:
    root = Path(users_root)
    if not root.is_dir():
        return []

    items = []
    for user_dir in _iter_dirs(root):
        clones_root = user_dir / "clones"
        if not clones_root.is_dir():
            continue
        for clone_dir in _iter_dirs(clones_root):
            items.append(_clone_resource_item(user_dir.name, clone_dir.name, clone_dir))

    items.sort(key=lambda item: (str(item["userId"]), str(item["cloneId"])))
    return items


def _clone_resource_item(user_id: str, clone_id: str, clone_dir: Path) -> dict[str, object]:
    vector_stats = _read_vector_stats(clone_dir)
    voice_stats = _read_voice_stats(clone_dir)
    return {
        "userId": user_id,
        "cloneId": clone_id,
        "cloneName": _read_clone_name(clone_dir / "profile" / "profile.json", clone_id),
        "vectorDbName": vector_stats["name"],
        "vectorDbSizeBytes": vector_stats["size_bytes"],
        "vectorChunkCount": vector_stats["chunk_count"],
        "voiceStatus": voice_stats["status"],
        "voiceSampleCount": voice_stats["sample_count"],
        "voiceModelSizeBytes": voice_stats["model_size_bytes"],
        "updatedAt": _updated_at(clone_dir),
    }


def _read_vector_stats(clone_dir: Path) -> dict[str, object]:
    vector_dir = _find_vector_dir(clone_dir)
    if vector_dir is None:
        return {"name": "", "size_bytes": 0, "chunk_count": 0}

    manifest = _read_json_object(_find_manifest_path(vector_dir))
    db_path = _vector_db_path(vector_dir, manifest)
    db_exists = db_path is not None and db_path.exists()
    return {
        "name": _first_string(
            manifest,
            "vectorDbName",
            "vector_db_name",
            "dbName",
            "db_name",
            "name",
        )
        or (vector_dir.name if db_exists else ""),
        "size_bytes": _path_size_bytes(db_path) if db_exists else 0,
        "chunk_count": _chunk_count(manifest),
    }


def _read_voice_stats(clone_dir: Path) -> dict[str, object]:
    voice_dir = clone_dir / "voice"
    status = _read_json_object(voice_dir / "status.json")
    model_size_bytes = _voice_model_size_bytes(voice_dir, status)
    sample_count = _voice_sample_count(voice_dir, status)
    return {
        "status": _first_string(status, "status") or _default_voice_status(sample_count, model_size_bytes),
        "sample_count": sample_count,
        "model_size_bytes": model_size_bytes,
    }


def _read_clone_name(profile_path: Path, default: str) -> str:
    profile = _read_json_object(profile_path)
    return (
        _first_string(profile, "cloneName", "clone_name", "targetName", "target_name", "name")
        or default
    )


def _find_vector_dir(clone_dir: Path) -> Path | None:
    for name in _VECTOR_DIR_NAMES:
        candidate = clone_dir / name
        if candidate.is_dir():
            return candidate

    for name in _VECTOR_MANIFEST_NAMES:
        if (clone_dir / name).is_file():
            return clone_dir

    if (clone_dir / "db").exists():
        return clone_dir
    return None


def _find_manifest_path(vector_dir: Path) -> Path | None:
    for name in _VECTOR_MANIFEST_NAMES:
        candidate = vector_dir / name
        if candidate.is_file():
            return candidate
    return None


def _vector_db_path(vector_dir: Path, manifest: dict[str, Any]) -> Path | None:
    configured_path = _first_string(
        manifest,
        "dbPath",
        "db_path",
        "indexPath",
        "index_path",
        "path",
    )
    if configured_path:
        candidate = Path(configured_path)
        if not candidate.is_absolute():
            candidate = vector_dir / candidate
        return candidate if _is_inside(candidate, vector_dir) else None

    for name in _VECTOR_DB_DIR_NAMES:
        candidate = vector_dir / name
        if candidate.exists():
            return candidate
    return None


def _voice_sample_count(voice_dir: Path, status: dict[str, Any]) -> int:
    count = _int_value(status.get("sample_count"), None)
    if count is None:
        count = _int_value(status.get("sampleCount"), None)
    if count is not None and count >= 0:
        return count

    sample_filenames = status.get("sample_filenames")
    if not isinstance(sample_filenames, list):
        sample_filenames = status.get("sampleFilenames")
    if isinstance(sample_filenames, list):
        return len([name for name in sample_filenames if str(name).strip()])

    sample_filename = _first_string(status, "sample_filename", "sampleFilename")
    if sample_filename:
        return 1

    if not voice_dir.is_dir():
        return 0
    return sum(1 for child in _iter_files(voice_dir) if _is_audio_sample_file(child))


def _voice_model_size_bytes(voice_dir: Path, status: dict[str, Any]) -> int:
    if not voice_dir.is_dir():
        return 0

    paths: list[Path] = []
    for key in (
        "modelPath",
        "model_path",
        "modelFile",
        "model_file",
        "checkpointPath",
        "checkpoint_path",
        "adapterPath",
        "adapter_path",
    ):
        paths.extend(_voice_model_paths(voice_dir, status.get(key)))

    for child in _iter_children(voice_dir):
        if child.is_dir() and child.name.lower() in _MODEL_DIR_NAMES:
            paths.append(child)
        elif child.is_file() and child.suffix.lower() in _MODEL_FILE_EXTENSIONS:
            paths.append(child)

    seen: set[Path] = set()
    total = 0
    for path in paths:
        if not _is_inside(path, voice_dir):
            continue
        for file_path in _files_for_size(path):
            resolved = _resolved(file_path)
            if resolved in seen:
                continue
            seen.add(resolved)
            total += _file_size(file_path)
    return total


def _voice_model_paths(voice_dir: Path, value: Any) -> list[Path]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, list):
        values = [str(item) for item in value if str(item).strip()]
    else:
        values = []

    paths = []
    for raw_path in values:
        path = Path(raw_path)
        if not path.is_absolute():
            path = voice_dir / path
        paths.append(path)
    return paths


def _chunk_count(manifest: dict[str, Any]) -> int:
    for key in ("chunkCount", "chunk_count", "vectorCount", "vector_count", "documentCount", "document_count"):
        count = _int_value(manifest.get(key), None)
        if count is not None and count >= 0:
            return count

    chunks = manifest.get("chunks")
    if isinstance(chunks, list):
        return len(chunks)
    count = _int_value(chunks, None)
    if count is not None and count >= 0:
        return count
    return 0


def _read_json_object(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _path_size_bytes(path: Path | None) -> int:
    if path is None:
        return 0
    if path.is_file() and not path.is_symlink():
        try:
            return path.stat().st_size
        except OSError:
            return 0
    if not path.is_dir() or path.is_symlink():
        return 0
    return sum(_file_size(child) for child in _iter_files(path))


def _files_for_size(path: Path):
    if path.is_file() and not path.is_symlink():
        yield path
    elif path.is_dir() and not path.is_symlink():
        yield from _iter_files(path)


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size if path.is_file() and not path.is_symlink() else 0
    except OSError:
        return 0


def _default_voice_status(sample_count: int, model_size_bytes: int) -> str:
    if model_size_bytes > 0:
        return "ready"
    if sample_count > 0:
        return "samples_ready"
    return "missing"


def _updated_at(path: Path) -> str:
    latest = _max_mtime(path)
    if latest is None:
        return ""
    return datetime.fromtimestamp(latest, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _max_mtime(path: Path) -> float | None:
    latest = _mtime(path)
    for child in path.rglob("*"):
        if child.is_symlink():
            continue
        child_mtime = _mtime(child)
        if child_mtime is not None and (latest is None or child_mtime > latest):
            latest = child_mtime
    return latest


def _mtime(path: Path) -> float | None:
    try:
        return path.stat().st_mtime
    except OSError:
        return None


def _first_string(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _int_value(value: Any, default: int | None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _is_audio_sample_file(path: Path) -> bool:
    return path.is_file() and path.name != "status.json" and path.suffix.lower() in _AUDIO_EXTENSIONS


def _is_inside(path: Path, base: Path) -> bool:
    try:
        path.resolve().relative_to(base.resolve())
    except (OSError, ValueError):
        return False
    return True


def _resolved(path: Path) -> Path:
    try:
        return path.resolve()
    except OSError:
        return path.absolute()


def _iter_dirs(path: Path):
    try:
        children = list(path.iterdir())
    except OSError:
        return
    for child in children:
        if child.is_dir() and not child.is_symlink():
            yield child


def _iter_children(path: Path):
    try:
        yield from path.iterdir()
    except OSError:
        return


def _iter_files(path: Path):
    try:
        children = list(path.rglob("*"))
    except OSError:
        return
    for child in children:
        if child.is_file() and not child.is_symlink():
            yield child
