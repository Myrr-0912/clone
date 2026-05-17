from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Mapping

from .chatlog import ChatMessage
from .llm import LLMSettings, Transport, load_env_file
from .models import CloneMemory, CloneProfile, CloneRules, CloneStyle
from .persona import build_clone_profile

_MAX_ANALYSIS_CHARS = 24000


def build_text_trained_profile(
    target_name: str,
    messages: list[ChatMessage],
    raw_text: str,
    clone_id: str | None = None,
    env_path: Path | None = None,
    env: Mapping[str, str] | None = None,
    transport: Transport | None = None,
) -> CloneProfile:
    """Build a clone profile, optionally using an LLM as the text trainer."""
    local_profile = build_clone_profile(target_name, messages, clone_id=clone_id)
    source = dict(os.environ if env is None else env)
    if env_path is not None:
        load_env_file(env_path, source)

    backend = source.get("TEXT_TRAINING_BACKEND", "").strip().lower()
    if backend == "local" or (not backend and source.get("LLM_BACKEND", "").strip().lower() == "local"):
        return _mark_backend(local_profile, "local")

    settings = LLMSettings.from_env(source)
    if not settings.enabled:
        return _mark_backend(local_profile, "local")

    if backend and backend not in {"llm", "deepseek"}:
        local_profile.source_stats["text_training_error"] = f"Unsupported TEXT_TRAINING_BACKEND: {backend}"
        return _mark_backend(local_profile, "local_fallback")

    analyzer = DeepSeekTextProfileAnalyzer(settings, source, transport=transport)
    try:
        return analyzer.analyze(target_name, messages, raw_text, fallback=local_profile)
    except Exception as exc:  # noqa: BLE001 - creation should stay usable if the trainer fails.
        local_profile.source_stats["text_training_error"] = str(exc)
        return _mark_backend(local_profile, "local_fallback")


class DeepSeekTextProfileAnalyzer:
    def __init__(
        self,
        settings: LLMSettings,
        env: Mapping[str, str] | None = None,
        transport: Transport | None = None,
    ) -> None:
        self.settings = settings
        self.env = env or {}
        self.transport = transport or _post_json

    def analyze(
        self,
        target_name: str,
        messages: list[ChatMessage],
        raw_text: str,
        fallback: CloneProfile,
    ) -> CloneProfile:
        payload = {
            "model": self.settings.model,
            "messages": [
                {"role": "system", "content": _analysis_system_prompt()},
                {
                    "role": "user",
                    "content": _analysis_user_prompt(target_name, messages, raw_text),
                },
            ],
            "temperature": _float_env(self.env.get("TEXT_TRAINING_TEMPERATURE"), 0.2),
            "max_tokens": _int_env(self.env.get("TEXT_TRAINING_MAX_TOKENS"), 2600),
            "stream": False,
        }
        response = self.transport(
            f"{self.settings.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            payload,
            _float_env(self.env.get("TEXT_TRAINING_TIMEOUT_SECONDS"), self.settings.timeout_seconds),
        )
        content = _extract_message(response)
        data = _parse_json_object(content)
        return _profile_from_llm_data(fallback, data, self.settings.model)


def make_text_profile_builder(env_path: Path):
    def build(target_name: str, messages: list[ChatMessage], raw_text: str) -> CloneProfile:
        return build_text_trained_profile(
            target_name=target_name,
            messages=messages,
            raw_text=raw_text,
            env_path=env_path,
        )

    return build


def _profile_from_llm_data(fallback: CloneProfile, data: dict[str, object], model: str) -> CloneProfile:
    memory_data = _dict_value(data.get("memory"))
    style_data = _dict_value(data.get("style"))
    rules_data = _dict_value(data.get("rules"))

    style = CloneStyle(
        catchphrases=_list_or(style_data.get("catchphrases"), fallback.style.catchphrases),
        particles=_string_list(style_data.get("particles")),
        punctuation=_list_or(style_data.get("punctuation"), fallback.style.punctuation),
        emoji_style=_string_list(style_data.get("emoji_style")),
        message_format=_string_list(style_data.get("message_format")),
        typing_habits=_string_list(style_data.get("typing_habits")),
        address_terms=_string_list(style_data.get("address_terms")),
        example_dialogues=_string_list(style_data.get("example_dialogues")),
        average_length=fallback.style.average_length,
    )
    memory = CloneMemory(
        key_topics=_list_or(memory_data.get("key_topics"), fallback.memory.key_topics),
        summary=_string_value(memory_data.get("summary")) or fallback.memory.summary,
        relationship_overview=_string_list(memory_data.get("relationship_overview")),
        timeline=_string_list(memory_data.get("timeline")),
        daily_patterns=_string_list(memory_data.get("daily_patterns")),
        shared_experiences=_string_list(memory_data.get("shared_experiences")),
        inside_jokes=_string_list(memory_data.get("inside_jokes")),
        food_preferences=_string_list(memory_data.get("food_preferences")),
        interests=_string_list(memory_data.get("interests")),
        conflict_patterns=_string_list(memory_data.get("conflict_patterns")),
        sweet_moments=_string_list(memory_data.get("sweet_moments")),
        breakup_notes=_string_list(memory_data.get("breakup_notes")),
    )
    rules = CloneRules(
        hard_rules=_string_list(rules_data.get("hard_rules")),
        identity=_string_list(rules_data.get("identity")),
        reply_cadence=_list_or(rules_data.get("reply_cadence"), fallback.rules.reply_cadence),
        address_terms=_list_or(rules_data.get("address_terms"), fallback.rules.address_terms),
        speech_style=_string_list(rules_data.get("speech_style")),
        emotional_patterns=_list_or(rules_data.get("emotional_patterns"), fallback.rules.emotional_patterns),
        relationship_behaviors=_list_or(
            rules_data.get("relationship_behaviors"),
            fallback.rules.relationship_behaviors,
        ),
        boundary_behaviors=_list_or(rules_data.get("boundary_behaviors"), fallback.rules.boundary_behaviors),
        attachment_style=_string_list(rules_data.get("attachment_style")),
        love_language=_string_list(rules_data.get("love_language")),
        anger_triggers=_string_list(rules_data.get("anger_triggers")),
        happy_triggers=_string_list(rules_data.get("happy_triggers")),
        sensitive_topics=_string_list(rules_data.get("sensitive_topics")),
    )
    stats = dict(fallback.source_stats)
    stats.update(
        {
            "text_training_backend": "llm",
            "text_training_model": model,
        }
    )
    return CloneProfile(
        clone_id=fallback.clone_id,
        name=fallback.name,
        style=style,
        memory=memory,
        rules=rules,
        source_stats=stats,
        voice=fallback.voice,
        corrections=list(fallback.corrections),
    )


def _analysis_system_prompt() -> str:
    return """你是一个文本画像训练器。参考 ex-skill 的 memory_analyzer、persona_analyzer、memory_builder 和 persona_builder 思路，把聊天记录蒸馏为可驱动对话的 Relationship Memory + 5 层 Persona。

抽取维度：
- Relationship Memory：关系概览、时间线、日常模式、共同经历、Inside Jokes、饮食偏好、兴趣爱好、争吵模式、甜蜜时刻、分手相关。
- Persona Layer 0：硬规则，不让角色突然完美、突然表白、突然无条件包容，除非原材料有证据。
- Persona Layer 1：身份锚定，只写原材料能支持的信息。
- Persona Layer 2：说话风格，包括语气词、标点、emoji、消息长度、打字习惯、口头禅、称呼方式、示例对话。
- Persona Layer 3：情感模式，包括表达爱意、生气、难过、开心、吃醋、安慰方式、依恋类型、爱的语言。
- Persona Layer 4：关系行为，包括关系角色、典型争吵模式、主动程度、回复速度、活跃时间段、边界与底线。

规则：
- 聊天记录事实优先于推测。
- 不得虚构私人经历；信息不足时写 [待补充]。
- 保留好的和不好的模式，不美化、不丑化。
- 输出必须是 UTF-8 JSON，不能有 markdown 代码块。
- 只返回 JSON，不要解释。

JSON schema：
{
  "memory": {
    "key_topics": ["..."],
    "summary": "...",
    "relationship_overview": ["..."],
    "timeline": ["..."],
    "daily_patterns": ["..."],
    "shared_experiences": ["..."],
    "inside_jokes": ["..."],
    "food_preferences": ["..."],
    "interests": ["..."],
    "conflict_patterns": ["..."],
    "sweet_moments": ["..."],
    "breakup_notes": ["..."]
  },
  "style": {
    "catchphrases": ["..."],
    "particles": ["..."],
    "punctuation": ["..."],
    "emoji_style": ["..."],
    "message_format": ["..."],
    "typing_habits": ["..."],
    "address_terms": ["..."],
    "example_dialogues": ["..."]
  },
  "rules": {
    "hard_rules": ["..."],
    "identity": ["..."],
    "reply_cadence": ["..."],
    "address_terms": ["..."],
    "speech_style": ["..."],
    "emotional_patterns": ["..."],
    "relationship_behaviors": ["..."],
    "boundary_behaviors": ["..."],
    "attachment_style": ["..."],
    "love_language": ["..."],
    "anger_triggers": ["..."],
    "happy_triggers": ["..."],
    "sensitive_topics": ["..."]
  }
}"""


def _analysis_user_prompt(target_name: str, messages: list[ChatMessage], raw_text: str) -> str:
    target_count = sum(1 for message in messages if message.is_target)
    clipped = raw_text.strip()
    if len(clipped) > _MAX_ANALYSIS_CHARS:
        clipped = f"{clipped[:_MAX_ANALYSIS_CHARS]}\n\n[材料已截断，原始字符数：{len(raw_text)}]"
    examples = _format_message_examples(messages)
    return "\n".join(
        [
            f"目标对象：{target_name}",
            f"解析消息数：{len(messages)}",
            f"目标对象消息数：{target_count}",
            "",
            "代表性消息：",
            examples or "[无]",
            "",
            "原始材料：",
            clipped or "[无]",
        ]
    )


def _format_message_examples(messages: list[ChatMessage]) -> str:
    lines = []
    for message in messages[:80]:
        prefix = message.timestamp or "no-time"
        role = "TARGET" if message.is_target else "OTHER"
        lines.append(f"- {prefix} {role} {message.speaker}: {message.text}")
    return "\n".join(lines)


def _mark_backend(profile: CloneProfile, backend: str) -> CloneProfile:
    profile.source_stats["text_training_backend"] = backend
    return profile


def _extract_message(response: dict[str, object]) -> str:
    try:
        choices = response["choices"]
        if not isinstance(choices, list) or not choices:
            raise KeyError("choices")
        first = choices[0]
        if not isinstance(first, dict):
            raise KeyError("choices[0]")
        message = first["message"]
        if not isinstance(message, dict):
            raise KeyError("message")
        content = message["content"]
    except KeyError as exc:
        raise RuntimeError("LLM text training response did not include a chat message") from exc
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("LLM text training response message was empty")
    return content.strip()


def _parse_json_object(content: str) -> dict[str, object]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise RuntimeError("LLM text training response was not valid JSON")
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise RuntimeError("LLM text training response must be a JSON object")
    return parsed


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list_or(value: object, fallback: list[str]) -> list[str]:
    values = _string_list(value)
    return values if values else list(fallback)


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _string_value(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _float_env(value: str | None, default: float) -> float:
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _int_env(value: str | None, default: int) -> int:
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _post_json(
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> dict[str, object]:
    from urllib import error, request

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(req, timeout=timeout) as response:
            decoded = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM text training failed with HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise RuntimeError(f"LLM text training failed: {exc.reason}") from exc

    if not isinstance(decoded, dict):
        raise RuntimeError("LLM text training response must be a JSON object")
    return decoded
