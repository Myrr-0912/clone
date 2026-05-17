from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Sequence

_MANIFEST_FIELDS = (
    "userId",
    "cloneId",
    "cloneName",
    "vectorDbPath",
    "status",
    "backend",
    "modelId",
    "jobId",
    "sampleCount",
    "sampleFilenames",
    "artifactPath",
    "updatedAt",
)


def create_or_update_voice_manifest(
    path: str | os.PathLike[str],
    *,
    user_id: str,
    clone_id: str,
    clone_name: str,
    vector_db_path: str | os.PathLike[str],
    status: str = "pending",
    backend: str = "none",
    model_id: str | None = None,
    job_id: str | None = None,
    sample_filenames: str | os.PathLike[str] | Sequence[str | os.PathLike[str]] | None = None,
    sample_count: int | None = None,
    artifact_path: str | os.PathLike[str] | None = None,
    updated_at: str | None = None,
) -> dict[str, object]:
    """Write a per-user, per-clone voice manifest and return its JSON data."""
    manifest_path = Path(path)
    existing = load_voice_manifest(manifest_path) if manifest_path.exists() else {}

    sample_names = (
        _clean_sample_filenames(sample_filenames)
        if sample_filenames is not None
        else _clean_sample_filenames(existing.get("sampleFilenames"))
    )
    artifact_value = (
        _path_value(artifact_path)
        if artifact_path is not None
        else _optional_string(existing.get("artifactPath"))
    )

    manifest = _ordered_manifest(
        {
            "userId": _required_string(user_id, "user_id"),
            "cloneId": _required_string(clone_id, "clone_id"),
            "cloneName": _required_string(clone_name, "clone_name"),
            "vectorDbPath": _required_string(_path_value(vector_db_path), "vector_db_path"),
            "status": _required_string(status, "status"),
            "backend": _required_string(backend, "backend"),
            "modelId": _optional_string(model_id),
            "jobId": _optional_string(job_id),
            "sampleCount": _count_value(sample_count, sample_names),
            "sampleFilenames": sample_names,
            "artifactPath": artifact_value,
            "updatedAt": _required_string(updated_at or _utc_now(), "updated_at"),
        }
    )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def load_voice_manifest(path: str | os.PathLike[str]) -> dict[str, object]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Voice manifest must be a JSON object")
    return _ordered_manifest(
        {
            "userId": _string_value(data.get("userId")),
            "cloneId": _string_value(data.get("cloneId")),
            "cloneName": _string_value(data.get("cloneName")),
            "vectorDbPath": _string_value(data.get("vectorDbPath")),
            "status": _string_value(data.get("status"), default="pending"),
            "backend": _string_value(data.get("backend"), default="none"),
            "modelId": _optional_string(data.get("modelId")),
            "jobId": _optional_string(data.get("jobId")),
            "sampleCount": _count_value(data.get("sampleCount"), _clean_sample_filenames(data.get("sampleFilenames"))),
            "sampleFilenames": _clean_sample_filenames(data.get("sampleFilenames")),
            "artifactPath": _optional_string(data.get("artifactPath")),
            "updatedAt": _string_value(data.get("updatedAt")),
        }
    )


def voice_artifact_size(path: str | os.PathLike[str] | None) -> int:
    if path is None:
        return 0
    try:
        artifact = Path(path)
        return artifact.stat().st_size if artifact.is_file() else 0
    except OSError:
        return 0


def voice_resource_summary(path: str | os.PathLike[str]) -> dict[str, object]:
    manifest_path = Path(path)
    manifest = load_voice_manifest(manifest_path)
    return {
        **manifest,
        "manifestPath": str(manifest_path),
        "artifactSize": voice_artifact_size(_optional_string(manifest.get("artifactPath"))),
    }


def _ordered_manifest(values: dict[str, object]) -> dict[str, object]:
    return {field: values[field] for field in _MANIFEST_FIELDS}


def _clean_sample_filenames(
    sample_filenames: object,
) -> list[str]:
    if sample_filenames is None:
        raw_names: Sequence[object] = []
    elif isinstance(sample_filenames, (str, os.PathLike)):
        raw_names = [sample_filenames]
    elif isinstance(sample_filenames, Sequence):
        raw_names = sample_filenames
    else:
        raw_names = []

    names = []
    for filename in raw_names:
        raw = str(os.fspath(filename) if isinstance(filename, os.PathLike) else filename).strip()
        if not raw:
            continue
        name = PureWindowsPath(PurePosixPath(raw).name).name.strip()
        if name:
            names.append(name)
    return names


def _path_value(path: str | os.PathLike[str]) -> str:
    return str(Path(path))


def _required_string(value: object, name: str) -> str:
    text = _string_value(value)
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_string(value: object) -> str | None:
    text = _string_value(value)
    return text or None


def _string_value(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _count_value(value: object, sample_names: list[str]) -> int:
    if value is None:
        return len(sample_names)
    try:
        count = int(value)
    except (TypeError, ValueError):
        return len(sample_names)
    return max(0, count)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
