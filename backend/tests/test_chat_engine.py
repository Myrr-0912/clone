import unittest

from app.services.chat_engine import LocalCloneChatEngine
from app.models.clone import CloneMemory, CloneProfile, CloneRules, CloneStyle


class ChatEngineTests(unittest.TestCase):
    def test_reply_uses_real_chinese_topic_and_style(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["哈哈哈"], punctuation=["？"], average_length=8),
            memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身。"),
            source_stats={"target_messages": 2},
        )

        reply = LocalCloneChatEngine().reply(profile, "你在干嘛？")

        self.assertIn("健身", reply.text)
        self.assertIn("哈哈哈", reply.text)
        self.assertNotIn("閸", reply.text)

    def test_reply_uses_clone_style(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["haha"], punctuation=[""], average_length=6),
            memory=CloneMemory(key_topics=["fitness"], summary="Likes workouts."),
            source_stats={"target_messages": 2},
        )

        reply = LocalCloneChatEngine().reply(profile, "what are you doing")

        self.assertIn("haha", reply.text)
        self.assertEqual(reply.clone_id, "abc")

    def test_reply_infers_emotion_for_voice_synthesis(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=[], punctuation=[], average_length=6),
            memory=CloneMemory(key_topics=[], summary=""),
            source_stats={"target_messages": 2},
        )

        reply = LocalCloneChatEngine().reply(profile, "I feel sad and lonely today")

        self.assertEqual(reply.emotion, "sad")

    def test_reply_respects_text_corrections_that_reject_catchphrases(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["哈哈哈"], punctuation=["。"], average_length=6),
            memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身"),
            source_stats={"target_messages": 2},
            corrections=["不要再说哈哈哈"],
        )

        reply = LocalCloneChatEngine().reply(profile, "你在干嘛？")

        self.assertNotIn("哈哈哈", reply.text)
        self.assertIn("健身", reply.text)

    def test_reply_uses_boundary_rules_when_user_pushes_for_response(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=[], punctuation=["。"], average_length=10),
            memory=CloneMemory(key_topics=[], summary=""),
            source_stats={"target_messages": 2},
            rules=CloneRules(boundary_behaviors=["忙时会先说明晚点回复，边界表达应克制清楚。"]),
        )

        reply = LocalCloneChatEngine().reply(profile, "你怎么又不回我")

        self.assertIn("晚点", reply.text)
        self.assertNotIn("哈哈哈", reply.text)
