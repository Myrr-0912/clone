import tempfile
import unittest
from pathlib import Path

from cyberclone.chatlog import ChatMessage
from cyberclone.storage import CloneStore
from cyberclone.text_training import build_text_trained_profile


class TextTrainingTests(unittest.TestCase):
    def test_llm_text_training_uses_ex_skill_dimensions_and_maps_profile(self):
        calls = []

        def fake_transport(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "choices": [
                    {
                        "message": {
                            "content": """
                            {
                              "memory": {
                                "key_topics": ["健身", "深夜聊天"],
                                "summary": "Target 经常深夜聊天，也会提到健身。",
                                "relationship_overview": ["关系类型：[待补充]"],
                                "timeline": ["2026-01-01 10:00 Target 提到健身"],
                                "daily_patterns": ["深夜聊天频率较高"],
                                "shared_experiences": ["一起聊过健身计划"],
                                "inside_jokes": ["[待补充]"],
                                "food_preferences": ["[待补充]"],
                                "interests": ["健身"],
                                "conflict_patterns": ["不想吵时会结束话题"],
                                "sweet_moments": ["会用宝宝安慰对方"],
                                "breakup_notes": ["[待补充]"]
                              },
                              "style": {
                                "catchphrases": ["哈哈哈"],
                                "particles": ["嗯"],
                                "punctuation": ["。"],
                                "emoji_style": ["很少使用 emoji"],
                                "message_format": ["短句连发"],
                                "typing_habits": ["口语化"],
                                "address_terms": ["宝宝"],
                                "example_dialogues": ["Target: 宝宝别难过，我在呢"]
                              },
                              "rules": {
                                "hard_rules": ["不突然变得无条件包容"],
                                "identity": ["名字/代号：Target"],
                                "reply_cadence": ["偏短句，可连发补充"],
                                "address_terms": ["宝宝"],
                                "speech_style": ["自然口语，不写长段作文"],
                                "emotional_patterns": ["安慰时先给陪伴感"],
                                "relationship_behaviors": ["会主动反问对方状态"],
                                "boundary_behaviors": ["忙时会说晚点回"],
                                "attachment_style": ["安全型倾向"],
                                "love_language": ["陪伴型"],
                                "anger_triggers": ["被连续追问"],
                                "happy_triggers": ["轻松玩笑"],
                                "sensitive_topics": ["分手原因"]
                              }
                            }
                            """
                        }
                    }
                ]
            }

        profile = build_text_trained_profile(
            target_name="Target",
            messages=[
                ChatMessage("Me", "你在干嘛", False, "2026-01-01 09:59"),
                ChatMessage("Target", "刚健身完 哈哈哈", True, "2026-01-01 10:00"),
            ],
            raw_text="Target: 刚健身完 哈哈哈",
            env={"DEEPSEEK_API_KEY": "sk-test"},
            transport=fake_transport,
        )

        self.assertEqual(profile.source_stats["text_training_backend"], "llm")
        self.assertIn("健身", profile.memory.key_topics)
        self.assertIn("深夜聊天频率较高", profile.memory.daily_patterns)
        self.assertIn("宝宝", profile.style.address_terms)
        self.assertIn("不突然变得无条件包容", profile.rules.hard_rules)
        self.assertIn("安全型倾向", profile.rules.attachment_style)

        _, headers, payload, timeout = calls[0]
        prompt = payload["messages"][0]["content"]
        self.assertEqual(headers["Authorization"], "Bearer sk-test")
        self.assertIn("Relationship Memory", prompt)
        self.assertIn("Layer 0", prompt)
        self.assertIn("争吵模式", prompt)
        self.assertIn("只返回 JSON", prompt)
        self.assertGreater(timeout, 0)

    def test_text_training_falls_back_to_local_profile_without_api_key(self):
        profile = build_text_trained_profile(
            target_name="Target",
            messages=[ChatMessage("Target", "刚健身完 哈哈哈", True, None)],
            raw_text="Target: 刚健身完 哈哈哈",
            env={},
        )

        self.assertEqual(profile.source_stats["text_training_backend"], "local")
        self.assertIn("健身", profile.memory.key_topics)

    def test_store_can_use_injected_text_profile_builder(self):
        with tempfile.TemporaryDirectory() as tmp:
            def fake_builder(target_name, messages, raw_text):
                profile = build_text_trained_profile(
                    target_name=target_name,
                    messages=messages,
                    raw_text=raw_text,
                    env={},
                )
                profile.source_stats["text_training_backend"] = "test-llm"
                return profile

            store = CloneStore(Path(tmp), text_profile_builder=fake_builder)
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: 刚健身完 哈哈哈",
            )

            self.assertEqual(clone.source_stats["text_training_backend"], "test-llm")
            self.assertTrue((Path(tmp) / clone.clone_id / "profile" / "memory.md").exists())
            self.assertTrue((Path(tmp) / clone.clone_id / "profile" / "persona.md").exists())

