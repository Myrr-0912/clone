from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from .chatlog import ChatMessage, parse_chat_log
from .models import CloneProfile, VoiceTrainingStatus
from .persona import (
    build_clone_profile,
    corrections_to_markdown,
    memory_to_markdown,
    profile_to_markdown,
    rules_to_markdown,
    style_to_markdown,
)
from .rag import (
    build_chat_index,
    chat_index_from_jsonable,
    chat_index_to_jsonable,
    format_retrieved_context,
    retrieve_relevant_messages,
)
from .resource_layout import clone_paths, ensure_clone_layout
from .vector_rag import index_clone_messages, retrieve_clone_evidence
from .vector_store import stats as vector_stats
from .voice import create_voice_training_status
from .voice_models import create_or_update_voice_manifest

TextProfileBuilder = Callable[[str, list[ChatMessage], str], CloneProfile]


class CloneStore:
    def __init__(
        self,
        root: Path,
        text_profile_builder: TextProfileBuilder | None = None,
        user_id: str | None = None,
    ):
        self.root = root
        self.text_profile_builder = text_profile_builder
        self.user_id = user_id
        self.root.mkdir(parents=True, exist_ok=True)

    def create_clone(
        self,
        target_name: str,
        chat_text: str,
        voice_filename: str = "",
        voice_bytes: bytes = b"",
        voice_files: list[tuple[str, bytes]] | None = None,
        image_files: list[tuple[str, bytes]] | None = None,
        video_files: list[tuple[str, bytes]] | None = None,
        sticker_files: list[tuple[str, bytes]] | None = None,
        moments_files: list[tuple[str, bytes]] | None = None,
    ) -> CloneProfile:
        voice_files = voice_files or []
        if voice_filename and voice_bytes:
            voice_files = [(voice_filename, voice_bytes), *voice_files]
        image_files = image_files or []
        video_files = video_files or []
        sticker_files = sticker_files or []
        moments_files = moments_files or []
        messages = parse_chat_log(chat_text, target_name)
        if self.text_profile_builder:
            profile = self.text_profile_builder(target_name, messages, chat_text)
        else:
            profile = build_clone_profile(target_name, messages)
        profile.source_stats["image_files"] = len(image_files)
        profile.source_stats["video_files"] = len(video_files)
        profile.source_stats["sticker_files"] = len(sticker_files)
        profile.source_stats["moments_files"] = len(moments_files)
        if self.user_id:
            profile.source_stats["user_id"] = self.user_id

        clone_dir = self._clone_dir(profile.clone_id, create=True)
        profile_dir = clone_dir / "profile"
        raw_dir = clone_dir / "raw"
        voice_dir = self._voice_samples_dir(profile.clone_id)
        image_dir = clone_dir / "images"
        video_dir = clone_dir / "videos"
        sticker_dir = clone_dir / "stickers"
        moments_dir = clone_dir / "moments"
        for directory in (profile_dir, raw_dir, voice_dir, image_dir, video_dir, sticker_dir, moments_dir):
            directory.mkdir(parents=True, exist_ok=True)

        (raw_dir / "chat.txt").write_text(chat_text, encoding="utf-8")
        (raw_dir / "chat_messages.json").write_text(
            json.dumps(chat_index_to_jsonable(build_chat_index(messages)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        saved_voice_names = self._write_files(voice_dir, voice_files)
        self._write_vector_index(profile, messages)
        self._write_files(image_dir, image_files)
        self._write_files(video_dir, video_files)
        for filename, file_bytes in sticker_files:
            if filename and file_bytes:
                (sticker_dir / Path(filename).name).write_bytes(file_bytes)
        self._write_files(moments_dir, moments_files)
        profile.voice = create_voice_training_status(saved_voice_names)
        profile.source_stats["voice_files"] = len(saved_voice_names)
        (self._voice_status_path(profile.clone_id)).write_text(
            json.dumps(asdict(profile.voice), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_voice_manifest(profile)

        self._write_profile_docs(profile)
        self._write_profile(profile)
        return profile

    def load_clone(self, clone_id: str) -> CloneProfile:
        profile_path = self._clone_dir(clone_id) / "profile" / "profile.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Clone profile not found: {clone_id}")
        return CloneProfile.from_dict(json.loads(profile_path.read_text(encoding="utf-8")))

    def list_clones(self) -> list[CloneProfile]:
        clones_dir = self._clones_dir()
        if not clones_dir.exists():
            return []

        profiles: list[CloneProfile] = []
        for clone_dir in sorted((path for path in clones_dir.iterdir() if path.is_dir()), key=lambda path: path.name):
            try:
                profiles.append(self.load_clone(clone_dir.name))
            except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError):
                continue
        return profiles

    def update_clone(
        self,
        clone_id: str,
        target_name: str | None = None,
        chat_text: str | None = None,
        voice_files: list[tuple[str, bytes]] | None = None,
        image_files: list[tuple[str, bytes]] | None = None,
        video_files: list[tuple[str, bytes]] | None = None,
        sticker_files: list[tuple[str, bytes]] | None = None,
        moments_files: list[tuple[str, bytes]] | None = None,
    ) -> CloneProfile:
        existing = self.load_clone(clone_id)
        clean_name = existing.name
        if target_name is not None:
            clean_name = target_name.strip()
            if not clean_name:
                raise ValueError("targetName is required")
        voice_files = voice_files or []
        image_files = image_files or []
        video_files = video_files or []
        sticker_files = sticker_files or []
        moments_files = moments_files or []

        if chat_text is None:
            profile = existing
            profile.name = clean_name
        else:
            messages = parse_chat_log(chat_text, clean_name)
            if self.text_profile_builder:
                profile = self.text_profile_builder(clean_name, messages, chat_text)
                profile.clone_id = clone_id
                profile.name = clean_name
            else:
                profile = build_clone_profile(clean_name, messages, clone_id=clone_id)
            profile.corrections = list(existing.corrections)
            profile.voice = existing.voice

            raw_dir = self._clone_dir(clone_id, create=True) / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)
            (raw_dir / "chat.txt").write_text(chat_text, encoding="utf-8")
            (raw_dir / "chat_messages.json").write_text(
                json.dumps(chat_index_to_jsonable(build_chat_index(messages)), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            self._write_vector_index(profile, messages)

        clone_dir = self._clone_dir(clone_id, create=True)
        media_specs = (
            ("image_files", clone_dir / "images", image_files),
            ("video_files", clone_dir / "videos", video_files),
            ("sticker_files", clone_dir / "stickers", sticker_files),
            ("moments_files", clone_dir / "moments", moments_files),
        )
        for stat_name, directory, files in media_specs:
            directory.mkdir(parents=True, exist_ok=True)
            self._write_files(directory, files)
            profile.source_stats[stat_name] = _count_files(directory)

        voice_dir = self._voice_samples_dir(clone_id)
        voice_dir.mkdir(parents=True, exist_ok=True)
        new_voice_names = self._write_files(voice_dir, voice_files)
        if new_voice_names or profile.voice is None:
            existing_voice_names = _voice_sample_names(existing.voice)
            profile.voice = create_voice_training_status(_unique_names([*existing_voice_names, *new_voice_names]))
        profile.source_stats["voice_files"] = len(_voice_sample_names(profile.voice))
        if self.user_id:
            profile.source_stats["user_id"] = self.user_id
        self._voice_status_path(clone_id).write_text(
            json.dumps(asdict(profile.voice), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_profile_docs(profile)
        self._write_voice_manifest(profile)
        self._write_profile(profile)
        return profile

    def delete_clone(self, clone_id: str) -> bool:
        clone_dir = self._clone_dir(clone_id)
        if not clone_dir.exists():
            return False

        root = self._clones_dir().resolve()
        target = clone_dir.resolve()
        if not _is_relative_to(target, root):
            raise ValueError("Clone path escapes the clone root")
        shutil.rmtree(target)
        return True

    def load_voice_status(self, clone_id: str) -> VoiceTrainingStatus:
        status_path = self._voice_status_path(clone_id)
        if not status_path.exists():
            raise FileNotFoundError(f"Voice status not found: {clone_id}")
        return VoiceTrainingStatus(**json.loads(status_path.read_text(encoding="utf-8")))

    def update_voice_status(self, clone_id: str, status: VoiceTrainingStatus) -> None:
        profile = self.load_clone(clone_id)
        profile.voice = status
        voice_dir = self._clone_dir(clone_id) / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        self._voice_status_path(clone_id).write_text(
            json.dumps(asdict(status), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_voice_manifest(profile)
        self._write_profile(profile)

    def add_voice_samples(self, clone_id: str, voice_files: list[tuple[str, bytes]]) -> CloneProfile:
        profile = self.load_clone(clone_id)
        voice_dir = self._voice_samples_dir(clone_id)
        voice_dir.mkdir(parents=True, exist_ok=True)

        new_names = self._write_files(voice_dir, voice_files)
        existing_names = profile.voice.sample_filenames if profile.voice else []
        sample_names = _unique_names([*existing_names, *new_names])
        profile.voice = create_voice_training_status(sample_names)
        profile.source_stats["voice_files"] = len(sample_names)
        self._voice_status_path(clone_id).write_text(
            json.dumps(asdict(profile.voice), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_voice_manifest(profile)
        self._write_profile(profile)
        return profile

    def add_text_correction(self, clone_id: str, correction: str) -> CloneProfile:
        profile = self.load_clone(clone_id)
        clean_correction = correction.strip()
        if not clean_correction:
            raise ValueError("Correction text is required")
        if clean_correction not in profile.corrections:
            profile.corrections.append(clean_correction)
        self._write_profile_docs(profile)
        self._write_profile(profile)
        return profile

    def retrieve_chat_context(self, clone_id: str, query: str, max_snippets: int = 8) -> str:
        if self.user_id:
            evidence = retrieve_clone_evidence(
                str(self._vector_db_path(clone_id)),
                self.user_id,
                clone_id,
                query,
                top_k=max_snippets,
            )
            if evidence:
                return evidence

        index_path = self._clone_dir(clone_id) / "raw" / "chat_messages.json"
        if not index_path.exists():
            self._backfill_chat_index(clone_id)
        if not index_path.exists():
            return ""
        records = chat_index_from_jsonable(json.loads(index_path.read_text(encoding="utf-8")))
        snippets = retrieve_relevant_messages(records, query, max_snippets=max_snippets)
        return format_retrieved_context(snippets)

    def _backfill_chat_index(self, clone_id: str) -> None:
        raw_path = self._clone_dir(clone_id) / "raw" / "chat.txt"
        if not raw_path.exists():
            return
        profile = self.load_clone(clone_id)
        messages = parse_chat_log(raw_path.read_text(encoding="utf-8"), profile.name)
        index_path = self._clone_dir(clone_id) / "raw" / "chat_messages.json"
        index_path.write_text(
            json.dumps(chat_index_to_jsonable(build_chat_index(messages)), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def voice_sample_paths(self, clone_id: str) -> list[Path]:
        profile = self.load_clone(clone_id)
        if not profile.voice:
            return []

        filenames = list(profile.voice.sample_filenames)
        if profile.voice.sample_filename:
            filenames.insert(0, profile.voice.sample_filename)

        sample_dir = self._voice_samples_dir(clone_id)
        sample_paths = []
        seen = set()
        for filename in filenames:
            sample_path = sample_dir / Path(filename).name
            if sample_path.is_file() and sample_path not in seen:
                sample_paths.append(sample_path)
                seen.add(sample_path)
        return sample_paths

    def _write_profile(self, profile: CloneProfile) -> None:
        profile_path = self._clone_dir(profile.clone_id, create=True) / "profile" / "profile.json"
        profile_path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_profile_docs(self, profile: CloneProfile) -> None:
        profile_dir = self._clone_dir(profile.clone_id, create=True) / "profile"
        profile_dir.mkdir(parents=True, exist_ok=True)
        (profile_dir / "persona.md").write_text(profile_to_markdown(profile), encoding="utf-8")
        (profile_dir / "style.md").write_text(style_to_markdown(profile), encoding="utf-8")
        (profile_dir / "memory.md").write_text(memory_to_markdown(profile), encoding="utf-8")
        (profile_dir / "rules.md").write_text(rules_to_markdown(profile), encoding="utf-8")
        (profile_dir / "corrections.md").write_text(corrections_to_markdown(profile), encoding="utf-8")

    def _write_files(self, directory: Path, files: list[tuple[str, bytes]]) -> list[str]:
        written_names = []
        reserved_names: set[str] = set()
        for filename, file_bytes in files:
            if filename and file_bytes:
                safe_name = _available_filename(directory, Path(filename).name, reserved_names)
                if not safe_name:
                    continue
                (directory / safe_name).write_bytes(file_bytes)
                written_names.append(safe_name)
                reserved_names.add(safe_name)
        return written_names

    def _write_vector_index(self, profile: CloneProfile, messages: list[ChatMessage]) -> None:
        if not self.user_id:
            return
        db_path = self._vector_db_path(profile.clone_id)
        index_clone_messages(str(db_path), self.user_id, profile.clone_id, messages, profile.name)
        summary = vector_stats(db_path)
        profile.source_stats["vector_db_name"] = f"{profile.name}-{profile.clone_id}"
        profile.source_stats["vector_db_path"] = str(db_path)
        profile.source_stats["vector_chunk_count"] = summary["chunk_count"]
        profile.source_stats["vector_db_size_bytes"] = summary["db_size_bytes"]
        manifest_path = clone_paths(self.root, self.user_id, profile.clone_id).vector_manifest_path
        manifest_path.write_text(
            json.dumps(
                {
                    "name": profile.source_stats["vector_db_name"],
                    "dbPath": db_path.name,
                    "chunkCount": summary["chunk_count"],
                    "dbSizeBytes": summary["db_size_bytes"],
                    "updatedAt": summary["updated_at"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def _write_voice_manifest(self, profile: CloneProfile) -> None:
        if not self.user_id:
            return
        paths = clone_paths(self.root, self.user_id, profile.clone_id)
        voice = profile.voice
        create_or_update_voice_manifest(
            paths.voice_model_manifest_path,
            user_id=self.user_id,
            clone_id=profile.clone_id,
            clone_name=profile.name,
            vector_db_path=paths.vector_db_path,
            status=voice.status if voice else "missing_samples",
            backend=voice.adapter if voice else "none",
            model_id=voice.model_id if voice else None,
            job_id=voice.job_id if voice else None,
            sample_filenames=voice.sample_filenames if voice else [],
            sample_count=voice.sample_count if voice else 0,
        )

    def _clone_dir(self, clone_id: str, create: bool = False) -> Path:
        if not self.user_id:
            clone_dir = self.root / clone_id
            if create:
                clone_dir.mkdir(parents=True, exist_ok=True)
            return clone_dir
        paths = ensure_clone_layout(self.root, self.user_id, clone_id) if create else clone_paths(self.root, self.user_id, clone_id)
        return paths.clone_dir

    def _clones_dir(self) -> Path:
        if not self.user_id:
            return self.root
        return clone_paths(self.root, self.user_id, "placeholder").clones_dir

    def _vector_db_path(self, clone_id: str) -> Path:
        if self.user_id:
            return clone_paths(self.root, self.user_id, clone_id).vector_db_path
        return self.root / clone_id / "vector" / "db.json"

    def _voice_samples_dir(self, clone_id: str) -> Path:
        if self.user_id:
            return clone_paths(self.root, self.user_id, clone_id).voice_samples_dir
        return self.root / clone_id / "voice"

    def _voice_status_path(self, clone_id: str) -> Path:
        return self._clone_dir(clone_id) / "voice" / "status.json"


def _unique_names(names: list[str]) -> list[str]:
    seen = set()
    unique = []
    for name in names:
        safe_name = Path(name).name.strip()
        if safe_name and safe_name not in seen:
            unique.append(safe_name)
            seen.add(safe_name)
    return unique


def _voice_sample_names(status: VoiceTrainingStatus | None) -> list[str]:
    if status is None:
        return []
    return _unique_names([*status.sample_filenames, status.sample_filename or ""])


def _count_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file())


def _available_filename(directory: Path, filename: str, reserved_names: set[str]) -> str:
    safe_name = Path(filename).name.strip()
    if not safe_name:
        return ""

    candidate = safe_name
    source_path = Path(safe_name)
    counter = 2
    while candidate in reserved_names or (directory / candidate).exists():
        if source_path.suffix:
            candidate = f"{source_path.stem}-{counter}{source_path.suffix}"
        else:
            candidate = f"{source_path.name}-{counter}"
        counter += 1
    return candidate


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
