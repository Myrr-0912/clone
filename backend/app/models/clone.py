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
    particles: list[str] = field(default_factory=list)
    punctuation: list[str] = field(default_factory=list)
    emoji_style: list[str] = field(default_factory=list)
    message_format: list[str] = field(default_factory=list)
    typing_habits: list[str] = field(default_factory=list)
    address_terms: list[str] = field(default_factory=list)
    example_dialogues: list[str] = field(default_factory=list)
    average_length: float = 0.0


@dataclass(slots=True)
class CloneMemory:
    key_topics: list[str] = field(default_factory=list)
    summary: str = ""
    relationship_overview: list[str] = field(default_factory=list)
    timeline: list[str] = field(default_factory=list)
    daily_patterns: list[str] = field(default_factory=list)
    shared_experiences: list[str] = field(default_factory=list)
    inside_jokes: list[str] = field(default_factory=list)
    food_preferences: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    conflict_patterns: list[str] = field(default_factory=list)
    sweet_moments: list[str] = field(default_factory=list)
    breakup_notes: list[str] = field(default_factory=list)


@dataclass(slots=True)
class CloneRules:
    hard_rules: list[str] = field(default_factory=list)
    identity: list[str] = field(default_factory=list)
    reply_cadence: list[str] = field(default_factory=list)
    address_terms: list[str] = field(default_factory=list)
    speech_style: list[str] = field(default_factory=list)
    emotional_patterns: list[str] = field(default_factory=list)
    relationship_behaviors: list[str] = field(default_factory=list)
    boundary_behaviors: list[str] = field(default_factory=list)
    attachment_style: list[str] = field(default_factory=list)
    love_language: list[str] = field(default_factory=list)
    anger_triggers: list[str] = field(default_factory=list)
    happy_triggers: list[str] = field(default_factory=list)
    sensitive_topics: list[str] = field(default_factory=list)


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
            style=_style_from_dict(data.get("style", {})),
            memory=_memory_from_dict(data.get("memory", {})),
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


def _style_from_dict(value: Any) -> CloneStyle:
    if not isinstance(value, dict):
        return CloneStyle()
    return CloneStyle(
        catchphrases=_string_list(value.get("catchphrases", [])),
        particles=_string_list(value.get("particles", [])),
        punctuation=_string_list(value.get("punctuation", [])),
        emoji_style=_string_list(value.get("emoji_style", [])),
        message_format=_string_list(value.get("message_format", [])),
        typing_habits=_string_list(value.get("typing_habits", [])),
        address_terms=_string_list(value.get("address_terms", [])),
        example_dialogues=_string_list(value.get("example_dialogues", [])),
        average_length=_float_value(value.get("average_length", 0.0)),
    )


def _memory_from_dict(value: Any) -> CloneMemory:
    if not isinstance(value, dict):
        return CloneMemory()
    return CloneMemory(
        key_topics=_string_list(value.get("key_topics", [])),
        summary=str(value.get("summary", "")).strip(),
        relationship_overview=_string_list(value.get("relationship_overview", [])),
        timeline=_string_list(value.get("timeline", [])),
        daily_patterns=_string_list(value.get("daily_patterns", [])),
        shared_experiences=_string_list(value.get("shared_experiences", [])),
        inside_jokes=_string_list(value.get("inside_jokes", [])),
        food_preferences=_string_list(value.get("food_preferences", [])),
        interests=_string_list(value.get("interests", [])),
        conflict_patterns=_string_list(value.get("conflict_patterns", [])),
        sweet_moments=_string_list(value.get("sweet_moments", [])),
        breakup_notes=_string_list(value.get("breakup_notes", [])),
    )


def _rules_from_dict(value: Any) -> CloneRules:
    if not isinstance(value, dict):
        return CloneRules()
    return CloneRules(
        hard_rules=_string_list(value.get("hard_rules", [])),
        identity=_string_list(value.get("identity", [])),
        reply_cadence=_string_list(value.get("reply_cadence", [])),
        address_terms=_string_list(value.get("address_terms", [])),
        speech_style=_string_list(value.get("speech_style", [])),
        emotional_patterns=_string_list(value.get("emotional_patterns", [])),
        relationship_behaviors=_string_list(value.get("relationship_behaviors", [])),
        boundary_behaviors=_string_list(value.get("boundary_behaviors", [])),
        attachment_style=_string_list(value.get("attachment_style", [])),
        love_language=_string_list(value.get("love_language", [])),
        anger_triggers=_string_list(value.get("anger_triggers", [])),
        happy_triggers=_string_list(value.get("happy_triggers", [])),
        sensitive_topics=_string_list(value.get("sensitive_topics", [])),
    )


def _float_value(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
