from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .chatlog import parse_chat_log
from .models import CloneProfile, VoiceTrainingStatus
from .persona import (
    build_clone_profile,
    corrections_to_markdown,
    memory_to_markdown,
    profile_to_markdown,
    rules_to_markdown,
    style_to_markdown,
)
from .voice import create_voice_training_status


class CloneStore:
    def __init__(self, root: Path):
        self.root = root
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
        profile = build_clone_profile(target_name, messages)
        profile.source_stats["image_files"] = len(image_files)
        profile.source_stats["video_files"] = len(video_files)
        profile.source_stats["sticker_files"] = len(sticker_files)
        profile.source_stats["moments_files"] = len(moments_files)

        clone_dir = self.root / profile.clone_id
        profile_dir = clone_dir / "profile"
        raw_dir = clone_dir / "raw"
        voice_dir = clone_dir / "voice"
        image_dir = clone_dir / "images"
        video_dir = clone_dir / "videos"
        sticker_dir = clone_dir / "stickers"
        moments_dir = clone_dir / "moments"
        for directory in (profile_dir, raw_dir, voice_dir, image_dir, video_dir, sticker_dir, moments_dir):
            directory.mkdir(parents=True, exist_ok=True)

        (raw_dir / "chat.txt").write_text(chat_text, encoding="utf-8")
        saved_voice_names = self._write_files(voice_dir, voice_files)
        self._write_files(image_dir, image_files)
        self._write_files(video_dir, video_files)
        for filename, file_bytes in sticker_files:
            if filename and file_bytes:
                (sticker_dir / Path(filename).name).write_bytes(file_bytes)
        self._write_files(moments_dir, moments_files)
        profile.voice = create_voice_training_status(saved_voice_names)
        profile.source_stats["voice_files"] = len(saved_voice_names)
        (voice_dir / "status.json").write_text(
            json.dumps(asdict(profile.voice), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        self._write_profile_docs(profile)
        self._write_profile(profile)
        return profile

    def load_clone(self, clone_id: str) -> CloneProfile:
        profile_path = self.root / clone_id / "profile" / "profile.json"
        if not profile_path.exists():
            raise FileNotFoundError(f"Clone profile not found: {clone_id}")
        return CloneProfile.from_dict(json.loads(profile_path.read_text(encoding="utf-8")))

    def load_voice_status(self, clone_id: str) -> VoiceTrainingStatus:
        status_path = self.root / clone_id / "voice" / "status.json"
        if not status_path.exists():
            raise FileNotFoundError(f"Voice status not found: {clone_id}")
        return VoiceTrainingStatus(**json.loads(status_path.read_text(encoding="utf-8")))

    def update_voice_status(self, clone_id: str, status: VoiceTrainingStatus) -> None:
        profile = self.load_clone(clone_id)
        profile.voice = status
        voice_dir = self.root / clone_id / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)
        (voice_dir / "status.json").write_text(
            json.dumps(asdict(status), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        self._write_profile(profile)

    def add_voice_samples(self, clone_id: str, voice_files: list[tuple[str, bytes]]) -> CloneProfile:
        profile = self.load_clone(clone_id)
        voice_dir = self.root / clone_id / "voice"
        voice_dir.mkdir(parents=True, exist_ok=True)

        new_names = self._write_files(voice_dir, voice_files)
        existing_names = profile.voice.sample_filenames if profile.voice else []
        sample_names = _unique_names([*existing_names, *new_names])
        profile.voice = create_voice_training_status(sample_names)
        profile.source_stats["voice_files"] = len(sample_names)
        (voice_dir / "status.json").write_text(
            json.dumps(asdict(profile.voice), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
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

    def _write_profile(self, profile: CloneProfile) -> None:
        profile_path = self.root / profile.clone_id / "profile" / "profile.json"
        profile_path.write_text(
            json.dumps(profile.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _write_profile_docs(self, profile: CloneProfile) -> None:
        profile_dir = self.root / profile.clone_id / "profile"
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


def _unique_names(names: list[str]) -> list[str]:
    seen = set()
    unique = []
    for name in names:
        safe_name = Path(name).name.strip()
        if safe_name and safe_name not in seen:
            unique.append(safe_name)
            seen.add(safe_name)
    return unique


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
