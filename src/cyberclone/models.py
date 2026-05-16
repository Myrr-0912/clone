from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class ChatMessage:
    speaker: str
    text: str
    is_target: bool
    timestamp: str | None = None


@dataclass(slots=True)
class CloneStyle:
    catchphrases: list[str] = field(default_factory=list)
    punctuation: list[str] = field(default_factory=list)
    average_length: float = 0.0


@dataclass(slots=True)
class CloneMemory:
    key_topics: list[str] = field(default_factory=list)
    summary: str = ""


@dataclass(slots=True)
class CloneRules:
    reply_cadence: list[str] = field(default_factory=list)
    address_terms: list[str] = field(default_factory=list)
    emotional_patterns: list[str] = field(default_factory=list)
    relationship_behaviors: list[str] = field(default_factory=list)
    boundary_behaviors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class VoiceTrainingStatus:
    status: str
    adapter: str
    message: str
    sample_filename: str | None = None
    sample_filenames: list[str] = field(default_factory=list)
    sample_count: int = 0
    error: str | None = None
    model_id: str | None = None
    job_id: str | None = None


@dataclass(slots=True)
class CloneProfile:
    clone_id: str
    name: str
    style: CloneStyle
    memory: CloneMemory
    source_stats: dict[str, Any] = field(default_factory=dict)
    rules: CloneRules = field(default_factory=CloneRules)
    voice: VoiceTrainingStatus | None = None
    corrections: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CloneProfile":
        voice_data = data.get("voice")
        return cls(
            clone_id=str(data["clone_id"]),
            name=str(data["name"]),
            style=CloneStyle(**data.get("style", {})),
            memory=CloneMemory(**data.get("memory", {})),
            source_stats=dict(data.get("source_stats", {})),
            rules=_rules_from_dict(data.get("rules", {})),
            voice=VoiceTrainingStatus(**voice_data) if voice_data else None,
            corrections=_string_list(data.get("corrections", [])),
        )


@dataclass(slots=True)
class ChatReply:
    clone_id: str
    text: str
    emotion: str = "natural"


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _rules_from_dict(value: Any) -> CloneRules:
    if not isinstance(value, dict):
        return CloneRules()
    return CloneRules(
        reply_cadence=_string_list(value.get("reply_cadence", [])),
        address_terms=_string_list(value.get("address_terms", [])),
        emotional_patterns=_string_list(value.get("emotional_patterns", [])),
        relationship_behaviors=_string_list(value.get("relationship_behaviors", [])),
        boundary_behaviors=_string_list(value.get("boundary_behaviors", [])),
    )
