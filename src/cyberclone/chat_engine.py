from __future__ import annotations

from .models import ChatReply, CloneProfile

_CORRECTION_MARKERS = (
    "ta不会这样说",
    "ta 不会这样说",
    "TA不会这样说",
    "他不会这样说",
    "她不会这样说",
    "不像他",
    "不像她",
    "不像ta",
    "不像 TA",
    "不要这样回",
    "不是这种语气",
)
_CORRECTION_TRIM_CHARS = " \t\r\n:：,，.。!！?？"
_REJECTION_HINTS = ("不要", "别", "不会", "不该", "不再", "别再", "不像", "不是")
_RESPONSE_PRESSURE_HINTS = ("怎么不回", "不回我", "回消息", "又不回", "别不回", "催")


class LocalCloneChatEngine:
    """A deterministic placeholder that uses the learned profile shape.

    The production slot for this class is an LLM prompt or fine-tuned adapter.
    Keeping it deterministic makes the MVP testable before API keys are added.
    """

    def reply(self, profile: CloneProfile, user_text: str, retrieved_context: str = "") -> ChatReply:
        correction = extract_text_correction(user_text)
        if correction:
            return ChatReply(
                clone_id=profile.clone_id,
                text="我记住了，后面会按这个调整。",
                emotion=infer_emotion(user_text),
            )

        boundary_reply = _build_boundary_reply(profile, user_text)
        if boundary_reply:
            return ChatReply(clone_id=profile.clone_id, text=boundary_reply, emotion=infer_emotion(user_text))

        phrase = _pick_allowed_phrase(profile)
        topic = _pick_topic(profile, user_text)
        core = _build_core_reply(profile.name, user_text, topic)
        text = f"{core} {phrase}".strip()
        return ChatReply(clone_id=profile.clone_id, text=text, emotion=infer_emotion(user_text))


def extract_text_correction(user_text: str) -> str | None:
    text = user_text.strip()
    if not text:
        return None

    folded = text.casefold()
    for marker in _CORRECTION_MARKERS:
        index = folded.find(marker.casefold())
        if index < 0:
            continue
        correction = text[index + len(marker) :].strip(_CORRECTION_TRIM_CHARS)
        return correction or text
    return None


def _pick_allowed_phrase(profile: CloneProfile) -> str:
    for phrase in profile.style.catchphrases:
        if not _phrase_rejected_by_corrections(phrase, profile.corrections):
            return phrase
    return ""


def _phrase_rejected_by_corrections(phrase: str, corrections: list[str]) -> bool:
    if not phrase:
        return False
    return any(phrase in correction and any(hint in correction for hint in _REJECTION_HINTS) for correction in corrections)


def _pick_topic(profile: CloneProfile, user_text: str) -> str | None:
    for topic in profile.memory.key_topics:
        if topic and topic in user_text:
            return topic
    return profile.memory.key_topics[0] if profile.memory.key_topics else None


def _build_boundary_reply(profile: CloneProfile, user_text: str) -> str | None:
    if not any(hint in user_text for hint in _RESPONSE_PRESSURE_HINTS):
        return None
    if not profile.rules.boundary_behaviors:
        return None
    for rule in profile.rules.boundary_behaviors:
        if "晚点" in rule:
            return "我在忙，晚点回你。"
    return "我现在有点忙，晚点再说。"


def _build_core_reply(name: str, user_text: str, topic: str | None) -> str:
    if "干嘛" in user_text or "做什么" in user_text or "what are you doing" in user_text.casefold():
        if topic:
            return f"我刚还在想{topic}这个事"
        return "我刚在处理点自己的事"
    if user_text.endswith("?") or user_text.endswith("？"):
        if topic:
            return f"我觉得还是得看{topic}这块"
        return "我觉得可以再具体聊聊"
    if topic:
        return f"{topic}这个我还挺有感觉的"
    return f"{name}收到，继续说"


def infer_emotion(user_text: str) -> str:
    normalized = user_text.casefold()
    emotion_keywords = (
        ("sad", ("sad", "lonely", "miss you", "tired", "难过", "低落", "想你", "累")),
        ("excited", ("excited", "amazing", "太好了", "兴奋", "激动")),
        ("happy", ("happy", "glad", "great", "开心", "哈哈", "笑")),
        ("calm", ("calm", "quiet", "relax", "平静", "安静", "放松")),
    )
    for emotion, keywords in emotion_keywords:
        if any(keyword in normalized for keyword in keywords):
            return emotion
    return "natural"
