"""Path layout helpers for per-user clone resources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SAFE_SEGMENT_PATTERN = re.compile(r"[^\w.-]+")


@dataclass(frozen=True)
class CloneResourcePaths:
    root_dir: Path
    users_dir: Path
    user_dir: Path
    clones_dir: Path
    clone_dir: Path
    profile_dir: Path
    raw_dir: Path
    vector_dir: Path
    vector_db_path: Path
    vector_manifest_path: Path
    voice_dir: Path
    voice_samples_dir: Path
    voice_model_dir: Path
    voice_model_manifest_path: Path
    voice_artifacts_dir: Path


def _safe_segment(value: str) -> str:
    segment = str(value).strip()
    for path_break in ('\\', '/', ':', '*', '?', '"', '<', '>', '|'):
        segment = segment.replace(path_break, "-")
    segment = _SAFE_SEGMENT_PATTERN.sub("_", segment)
    segment = re.sub(r"[-_]+", lambda match: "-" if "-" in match.group(0) else "_", segment)
    segment = segment.strip("._-")
    if not segment:
        raise ValueError("path segment must contain at least one safe character")
    return segment


def clone_paths(root: str | Path, user_id: str, clone_id: str) -> CloneResourcePaths:
    root_dir = Path(root)
    users_dir = root_dir / "users"
    user_dir = users_dir / _safe_segment(user_id)
    clones_dir = user_dir / "clones"
    clone_dir = clones_dir / _safe_segment(clone_id)
    profile_dir = clone_dir / "profile"
    raw_dir = clone_dir / "raw"
    vector_dir = clone_dir / "vector"
    voice_dir = clone_dir / "voice"
    voice_model_dir = voice_dir / "model"

    return CloneResourcePaths(
        root_dir=root_dir,
        users_dir=users_dir,
        user_dir=user_dir,
        clones_dir=clones_dir,
        clone_dir=clone_dir,
        profile_dir=profile_dir,
        raw_dir=raw_dir,
        vector_dir=vector_dir,
        vector_db_path=vector_dir / "db.json",
        vector_manifest_path=vector_dir / "manifest.json",
        voice_dir=voice_dir,
        voice_samples_dir=voice_dir / "samples",
        voice_model_dir=voice_model_dir,
        voice_model_manifest_path=voice_model_dir / "manifest.json",
        voice_artifacts_dir=voice_model_dir / "artifacts",
    )


def ensure_clone_layout(root: str | Path, user_id: str, clone_id: str) -> CloneResourcePaths:
    paths = clone_paths(root, user_id, clone_id)
    for directory in (
        paths.profile_dir,
        paths.raw_dir,
        paths.vector_dir,
        paths.voice_samples_dir,
        paths.voice_artifacts_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)
    return paths
