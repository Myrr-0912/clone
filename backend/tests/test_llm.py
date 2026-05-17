import tempfile
import unittest
from pathlib import Path

from app.services.llm import DeepSeekChatEngine, LLMSettings, create_chat_engine, load_env_file
from app.services.chat_engine import LocalCloneChatEngine
from app.models.clone import CloneMemory, CloneProfile, CloneStyle


class LLMTests(unittest.TestCase):
    def test_load_env_file_sets_missing_values_without_overwriting_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            env_path = Path(tmp) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "DEEPSEEK_API_KEY=from-file",
                        "LLM_MODEL=deepseek-v4-flash",
                        "EMPTY_VALUE=",
                    ]
                ),
                encoding="utf-8",
            )
            env = {"DEEPSEEK_API_KEY": "already-set"}

            load_env_file(env_path, env)

            self.assertEqual(env["DEEPSEEK_API_KEY"], "already-set")
            self.assertEqual(env["LLM_MODEL"], "deepseek-v4-flash")
            self.assertEqual(env["EMPTY_VALUE"], "")

    def test_settings_from_env_enables_deepseek_defaults(self):
        settings = LLMSettings.from_env({"DEEPSEEK_API_KEY": "sk-test"})

        self.assertTrue(settings.enabled)
        self.assertEqual(settings.api_key, "sk-test")
        self.assertEqual(settings.base_url, "https://api.deepseek.com")
        self.assertEqual(settings.model, "deepseek-v4-flash")

    def test_create_chat_engine_falls_back_without_api_key(self):
        engine = create_chat_engine(env={})

        self.assertIsInstance(engine, LocalCloneChatEngine)

    def test_create_chat_engine_allows_forcing_local_backend(self):
        engine = create_chat_engine(
            env={
                "LLM_BACKEND": "local",
                "DEEPSEEK_API_KEY": "sk-test",
            }
        )

        self.assertIsInstance(engine, LocalCloneChatEngine)

    def test_deepseek_engine_sends_profile_prompt(self):
        calls = []

        def fake_transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"choices": [{"message": {"content": "LLM reply"}}]}

        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["haha"], punctuation=["!"], average_length=6),
            memory=CloneMemory(key_topics=["fitness"], summary="Likes workouts."),
            source_stats={"target_messages": 2},
        )
        settings = LLMSettings(api_key="sk-test", model="deepseek-v4-flash")

        reply = DeepSeekChatEngine(settings, transport=fake_transport).reply(profile, "hi")

        self.assertEqual(reply.clone_id, "abc")
        self.assertEqual(reply.text, "LLM reply")
        url, headers, payload, timeout = calls[0]
        self.assertEqual(url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertIn("Target", payload["messages"][0]["content"])
        self.assertIn("fitness", payload["messages"][0]["content"])
        self.assertIn("Part A - Relationship Memory", payload["messages"][0]["content"])
        self.assertIn("Part B - Persona", payload["messages"][0]["content"])
        self.assertIn("Hard rules", payload["messages"][0]["content"])
        self.assertIn("Speech style", payload["messages"][0]["content"])
        self.assertEqual(payload["messages"][1]["content"], "hi")
        self.assertGreater(timeout, 0)

    def test_deepseek_engine_infers_reply_emotion_for_voice_mode(self):
        def fake_transport(url, headers, payload, timeout):
            return {"choices": [{"message": {"content": "嗯，我听着。"}}]}

        reply = DeepSeekChatEngine(
            LLMSettings(api_key="sk-test"),
            transport=fake_transport,
        ).reply(_profile(), "我今天有点难过")

        self.assertEqual(reply.text, "嗯，我听着。")
        self.assertEqual(reply.emotion, "sad")


def _profile() -> CloneProfile:
    return CloneProfile(
        clone_id="abc",
        name="Target",
        style=CloneStyle(catchphrases=["哈哈哈"], punctuation=["。"], average_length=6),
        memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身"),
        source_stats={"target_messages": 2},
    )
