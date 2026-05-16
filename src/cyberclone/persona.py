from __future__ import annotations

from collections import Counter
import re
from uuid import uuid4

from .models import ChatMessage, CloneMemory, CloneProfile, CloneRules, CloneStyle

_CATCHPHRASE_RE = re.compile(r"(哈{2,}|嗯{2,}|啊{2,}|hh+|233+|[!！?？~～]{2,})", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+-]{2,}")
_STOPWORDS = {
    "这个",
    "那个",
    "就是",
    "然后",
    "因为",
    "所以",
    "不是",
    "可以",
    "没有",
    "现在",
    "一下",
    "感觉",
    "我们",
    "你们",
    "他们",
    "哈哈",
    "哈哈哈",
}
_TOPIC_HINTS = (
    "健身",
    "游戏",
    "电影",
    "工作",
    "学习",
    "音乐",
    "旅行",
    "创业",
    "代码",
    "产品",
    "设计",
    "吃饭",
    "睡觉",
)
_ADDRESS_TERMS = ("宝宝", "宝贝", "亲爱的", "老婆", "老公", "乖乖", "宝")
_COMFORT_HINTS = ("别难过", "别哭", "抱抱", "我在", "没事", "辛苦", "早点睡")
_CONFLICT_HINTS = ("算了", "不想吵", "随便", "你非要", "别这样", "冷静")
_PROACTIVE_HINTS = ("你呢", "吃了吗", "在干嘛", "到家", "睡了吗", "怎么样")
_BOUNDARY_HINTS = ("晚点", "在忙", "别催", "先不聊", "等下", "回头", "没空")


def build_clone_profile(
    target_name: str,
    messages: list[ChatMessage],
    clone_id: str | None = None,
) -> CloneProfile:
    target_messages = [message for message in messages if message.is_target]
    texts = [message.text for message in target_messages]
    joined = "\n".join(texts)

    style = CloneStyle(
        catchphrases=_extract_catchphrases(texts),
        punctuation=_extract_punctuation(texts),
        average_length=_average_length(texts),
    )
    memory = CloneMemory(
        key_topics=_extract_topics(joined),
        summary=_build_summary(target_name, texts),
    )
    rules = _extract_rules(messages, texts, style)

    return CloneProfile(
        clone_id=clone_id or uuid4().hex[:12],
        name=target_name,
        style=style,
        memory=memory,
        rules=rules,
        source_stats={
            "messages": len(messages),
            "target_messages": len(target_messages),
            "average_target_length": round(style.average_length, 2),
        },
    )


def profile_to_markdown(profile: CloneProfile) -> str:
    catchphrases = "、".join(profile.style.catchphrases) or "暂无稳定口头禅"
    topics = "、".join(profile.memory.key_topics) or "暂无稳定话题"
    punctuation = "、".join(profile.style.punctuation) or "普通"
    corrections = _corrections_to_markdown(profile.corrections)
    return "\n".join(
        [
            f"# {profile.name}",
            "",
            "## Part A - Relationship Memory",
            f"- 关键话题：{topics}",
            f"- 摘要：{profile.memory.summary}",
            "",
            "## Part B - Persona",
            "",
            "### Hard Rules",
            "- 只使用已提取的记忆、话题和说话风格作为约束，不编造未提供的私人经历。",
            "- 保持自然短句；被问到身份时明确这是 AI 合成的角色模拟。",
            "- 遇到危险、骚扰或越界请求时，优先给出克制且安全的回应。",
            "",
            "### Identity",
            f"- 名称：{profile.name}",
            f"- 目标消息数量：{profile.source_stats.get('target_messages', 0)}",
            "",
            "### Speech Style",
            f"- 高频口头禅：{catchphrases}",
            f"- 常用标点：{punctuation}",
            f"- 平均单条长度：{profile.style.average_length:.1f} 字符",
            "",
            "### Emotional Patterns",
            "- 优先贴近用户当前情绪，但避免过度承诺或强行亲密。",
            "- 情绪表达应通过语气、节奏和短句体现，而不是解释自己在模仿情绪。",
            "",
            "### Relationship Behavior",
            "- 用户提到关键话题时，优先围绕对应记忆线索回应。",
            "- 没有足够上下文时，用目标对象的语气继续追问，而不是生成确定事实。",
            "",
            "### Behavior Rules",
            _rules_to_markdown(profile.rules),
            "",
            "## Part C - Corrections",
            corrections,
        ]
    )


def profile_to_system_prompt(profile: CloneProfile) -> str:
    catchphrases = ", ".join(profile.style.catchphrases) or "none"
    punctuation = ", ".join(profile.style.punctuation) or "normal"
    topics = ", ".join(profile.memory.key_topics) or "none"
    corrections = "\n".join(f"- {correction}" for correction in profile.corrections) or "- none"
    return "\n".join(
        [
            f"You are roleplaying as {profile.name}.",
            "Reply in the same language as the user.",
            "Keep the reply natural, concise, and conversational.",
            "Use the layered profile below as constraints.",
            "",
            "Part A - Relationship Memory",
            f"- Key topics: {topics}.",
            f"- Memory summary: {profile.memory.summary}",
            "",
            "Part B - Persona",
            "Hard rules",
            "- Do not invent private experiences beyond the supplied memory and style signals.",
            "- If asked what you are, say this is an AI-generated character simulation.",
            "- Refuse unsafe, harassing, or privacy-invasive requests.",
            "Identity",
            f"- Name: {profile.name}.",
            f"- Learned target messages: {profile.source_stats.get('target_messages', 0)}.",
            "Speech style",
            f"- Known catchphrases: {catchphrases}.",
            f"- Common punctuation style: {punctuation}.",
            f"- Average message length: {profile.style.average_length:.1f} characters.",
            "Emotional patterns",
            "- Match the user's emotional temperature without overpromising intimacy.",
            "- Show emotion through wording and rhythm, not through meta-explanations.",
            "Relationship behavior",
            "- When the user mentions a key topic, ground the reply in the memory summary and topics.",
            "- When context is insufficient, ask a short in-character follow-up instead of asserting facts.",
            "Behavior rules",
            _rules_to_prompt(profile.rules),
            "",
            "Part C - Corrections",
            corrections,
        ]
    )


def style_to_markdown(profile: CloneProfile) -> str:
    return "\n".join(
        [
            "# Style",
            "",
            f"catchphrases: {', '.join(profile.style.catchphrases)}",
            f"punctuation: {', '.join(profile.style.punctuation)}",
            f"average_length: {profile.style.average_length:.2f}",
        ]
    )


def memory_to_markdown(profile: CloneProfile) -> str:
    return "\n".join(
        [
            "# Memory",
            "",
            f"topics: {', '.join(profile.memory.key_topics)}",
            "",
            profile.memory.summary,
        ]
    )


def corrections_to_markdown(profile: CloneProfile) -> str:
    return "\n".join(["# Corrections", "", _corrections_to_markdown(profile.corrections)])


def rules_to_markdown(profile: CloneProfile) -> str:
    catchphrases = "、".join(profile.style.catchphrases) or "暂无稳定口头禅"
    topics = "、".join(profile.memory.key_topics) or "暂无稳定话题"
    corrections = _corrections_to_markdown(profile.corrections)
    return "\n".join(
        [
            "# Rules",
            "",
            "## Hard Rules",
            "- 只使用已提取的记忆、话题和说话风格作为约束，不编造未提供的私人经历。",
            "- 被问到身份时明确这是 AI 合成的角色模拟。",
            "- 遇到危险、骚扰或越界请求时，优先给出克制且安全的回应。",
            "",
            "## Speech Constraints",
            f"- 高频口头禅：{catchphrases}",
            f"- 平均单条长度：{profile.style.average_length:.1f} 字符",
            "- 已被用户纠正或否定的表达必须避免重复出现。",
            "",
            "## Reply Cadence",
            _markdown_list(profile.rules.reply_cadence, "暂无稳定回复节奏。"),
            "",
            "## Address Terms",
            _markdown_list(profile.rules.address_terms, "暂无稳定称呼。"),
            "",
            "## Memory Grounding",
            f"- 关键话题：{topics}",
            "- 用户提到关键话题时，优先围绕对应记忆线索回应。",
            "- 没有足够上下文时，用目标对象的语气继续追问，而不是生成确定事实。",
            "",
            "## Emotional Patterns",
            _markdown_list(profile.rules.emotional_patterns, "暂无稳定情绪模式。"),
            "",
            "## Relationship Behavior",
            _markdown_list(profile.rules.relationship_behaviors, "暂无稳定关系行为。"),
            "",
            "## Boundary Behavior",
            _markdown_list(profile.rules.boundary_behaviors, "暂无稳定边界表达。"),
            "",
            "## Emotional Guardrails",
            "- 优先贴近用户当前情绪，但避免过度承诺或强行亲密。",
            "- 情绪表达应通过语气、节奏和短句体现，而不是解释自己在模仿情绪。",
            "",
            "## User Corrections",
            corrections,
        ]
    )


def _corrections_to_markdown(corrections: list[str]) -> str:
    if not corrections:
        return "- 暂无用户纠正。"
    return "\n".join(f"- {correction}" for correction in corrections)


def _rules_to_markdown(rules: CloneRules) -> str:
    blocks = [
        ("Reply Cadence", rules.reply_cadence),
        ("Address Terms", rules.address_terms),
        ("Emotional Patterns", rules.emotional_patterns),
        ("Relationship Behavior", rules.relationship_behaviors),
        ("Boundary Behavior", rules.boundary_behaviors),
    ]
    lines: list[str] = []
    for heading, items in blocks:
        if not items:
            continue
        lines.append(f"#### {heading}")
        lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) if lines else "- 暂无稳定行为规则。"


def _rules_to_prompt(rules: CloneRules) -> str:
    blocks = [
        ("Reply cadence", rules.reply_cadence),
        ("Address terms", rules.address_terms),
        ("Emotional patterns", rules.emotional_patterns),
        ("Relationship behavior", rules.relationship_behaviors),
        ("Boundary behavior", rules.boundary_behaviors),
    ]
    lines: list[str] = []
    for heading, items in blocks:
        if not items:
            continue
        lines.append(f"{heading}:")
        lines.extend(f"- {item}" for item in items)
    return "\n".join(lines) if lines else "- none"


def _markdown_list(items: list[str], fallback: str) -> str:
    if not items:
        return f"- {fallback}"
    return "\n".join(f"- {item}" for item in items)


def _extract_rules(messages: list[ChatMessage], texts: list[str], style: CloneStyle) -> CloneRules:
    joined = "\n".join(texts)
    return CloneRules(
        reply_cadence=_extract_reply_cadence(messages, style),
        address_terms=_extract_address_terms(joined),
        emotional_patterns=_extract_emotional_patterns(joined),
        relationship_behaviors=_extract_relationship_behaviors(joined),
        boundary_behaviors=_extract_boundary_behaviors(joined),
    )


def _extract_reply_cadence(messages: list[ChatMessage], style: CloneStyle) -> list[str]:
    rules: list[str] = []
    if style.average_length and style.average_length <= 12:
        rules.append("偏短句，适合用 1-2 个短句回应。")
    elif style.average_length >= 40:
        rules.append("可以使用较完整的长句，但仍保持聊天口吻。")
    if _max_target_run(messages) >= 2:
        rules.append("有连续补充消息习惯，可以短句连发但不要刷屏。")
    return rules


def _extract_address_terms(joined: str) -> list[str]:
    return [term for term in _ADDRESS_TERMS if term in joined]


def _extract_emotional_patterns(joined: str) -> list[str]:
    rules: list[str] = []
    if _has_any(joined, _COMFORT_HINTS):
        rules.append("安慰时优先给陪伴感，例如“别难过 / 我在”。")
    if _has_any(joined, _CONFLICT_HINTS):
        rules.append("冲突时倾向降温或结束争执，例如“算了 / 不想吵”。")
    if "哈哈" in joined or "开心" in joined:
        rules.append("开心时可以增加轻松语气，但不要强行热闹。")
    return rules


def _extract_relationship_behaviors(joined: str) -> list[str]:
    rules: list[str] = []
    if _has_any(joined, _PROACTIVE_HINTS):
        rules.append("关系互动中会主动反问和照看状态，例如“你呢 / 吃了吗”。")
    return rules


def _extract_boundary_behaviors(joined: str) -> list[str]:
    if _has_any(joined, _BOUNDARY_HINTS):
        return ["忙时会先说明晚点回复，边界表达应克制清楚。"]
    return []


def _max_target_run(messages: list[ChatMessage]) -> int:
    max_run = 0
    current = 0
    for message in messages:
        if message.is_target:
            current += 1
            max_run = max(max_run, current)
        else:
            current = 0
    return max_run


def _has_any(text: str, hints: tuple[str, ...]) -> bool:
    return any(hint in text for hint in hints)


def _extract_catchphrases(texts: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(match.group(1) for match in _CATCHPHRASE_RE.finditer(text))

    catchphrases = [phrase for phrase, _ in counter.most_common(8)]
    if "哈哈哈" in "\n".join(texts) and "哈哈哈" not in catchphrases:
        catchphrases.insert(0, "哈哈哈")
    return catchphrases[:8]


def _extract_punctuation(texts: list[str]) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(char for char in text if char in "。！？!?～~…")
    return [punctuation for punctuation, _ in counter.most_common(5)]


def _average_length(texts: list[str]) -> float:
    if not texts:
        return 0.0
    return sum(len(text) for text in texts) / len(texts)


def _extract_topics(joined: str) -> list[str]:
    counter: Counter[str] = Counter()
    for hint in _TOPIC_HINTS:
        if hint in joined:
            counter[hint] += joined.count(hint) + 3

    for token in _TOKEN_RE.findall(joined):
        if token not in _STOPWORDS and not _CATCHPHRASE_RE.fullmatch(token):
            counter[token] += 1

    return [topic for topic, _ in counter.most_common(10)]


def _build_summary(target_name: str, texts: list[str]) -> str:
    if not texts:
        return f"{target_name} 的聊天记录里暂时没有可学习的目标消息。"

    sample = " / ".join(texts[:3])
    return f"基于 {len(texts)} 条目标消息生成。代表性表达：{sample}"
