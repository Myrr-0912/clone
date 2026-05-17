import unittest

from app.services.chatlog import ChatMessage
from app.services.persona import build_clone_profile, profile_to_markdown, profile_to_system_prompt, rules_to_markdown


class PersonaTests(unittest.TestCase):
    def test_builds_real_chinese_style_and_memory_from_target_messages(self):
        messages = [
            ChatMessage("Me", "你在干嘛？", False, None),
            ChatMessage("Target", "刚吃完饭 哈哈哈", True, None),
            ChatMessage("Target", "等下去健身，顺便听音乐！！", True, None),
        ]

        profile = build_clone_profile("Target", messages)

        self.assertIn("哈哈哈", profile.style.catchphrases)
        self.assertIn("健身", profile.memory.key_topics)
        self.assertIn("音乐", profile.memory.key_topics)
        self.assertIn("刚吃完饭 哈哈哈", profile.memory.summary)

    def test_profile_markdown_uses_readable_chinese_layers(self):
        profile = build_clone_profile(
            "Target",
            [
                ChatMessage("Me", "还记得健身房吗？", False, None),
                ChatMessage("Target", "当然啊哈哈哈，健身完还去吃饭", True, None),
            ],
            clone_id="abc",
        )

        markdown = profile_to_markdown(profile)

        self.assertIn("## Part A - Relationship Memory", markdown)
        self.assertIn("## Part B - Persona", markdown)
        self.assertIn("关键话题：健身", markdown)
        self.assertIn("高频口头禅：哈哈哈", markdown)
        self.assertIn("AI 合成的角色模拟", markdown)

    def test_builds_style_and_memory_from_target_messages(self):
        messages = [
            ChatMessage("Me", "你在干嘛", False, None),
            ChatMessage("Target", "刚吃完饭 哈哈哈", True, None),
            ChatMessage("Target", "等下去健身 哈哈哈", True, None),
        ]

        profile = build_clone_profile("Target", messages)

        self.assertEqual(profile.name, "Target")
        self.assertIn("哈哈哈", profile.style.catchphrases)
        self.assertIn("健身", profile.memory.key_topics)
        self.assertGreater(profile.style.average_length, 0)

    def test_profile_markdown_uses_memory_and_persona_layers(self):
        messages = [
            ChatMessage("Me", "还记得健身房吗", False, None),
            ChatMessage("Target", "当然啊 哈哈哈，健身完还去吃饭", True, None),
            ChatMessage("Target", "我说话就这样！！", True, None),
        ]

        profile = build_clone_profile("Target", messages, clone_id="abc")
        markdown = profile_to_markdown(profile)

        for heading in (
            "## Part A - Relationship Memory",
            "## Part B - Persona",
            "### Hard Rules",
            "### Identity",
            "### Speech Style",
            "### Emotional Patterns",
            "### Relationship Behavior",
        ):
            self.assertIn(heading, markdown)
        self.assertIn("健身", markdown)
        self.assertIn("哈哈哈", markdown)

    def test_system_prompt_includes_text_correction_layer(self):
        profile = build_clone_profile(
            "Target",
            [
                ChatMessage("Me", "你在干嘛", False, None),
                ChatMessage("Target", "刚吃完饭 哈哈哈", True, None),
            ],
            clone_id="abc",
        )
        profile.corrections.append("不要再说哈哈哈")

        prompt = profile_to_system_prompt(profile)

        self.assertIn("Part C - Corrections", prompt)
        self.assertIn("不要再说哈哈哈", prompt)

    def test_rules_markdown_extracts_standalone_persona_constraints(self):
        profile = build_clone_profile(
            "Target",
            [
                ChatMessage("Me", "你在干嘛", False, None),
                ChatMessage("Target", "刚吃完饭 哈哈哈", True, None),
            ],
            clone_id="abc",
        )
        profile.corrections.append("不要再说哈哈哈")

        markdown = rules_to_markdown(profile)

        self.assertIn("# Rules", markdown)
        self.assertIn("Hard Rules", markdown)
        self.assertIn("Speech Constraints", markdown)
        self.assertIn("不要再说哈哈哈", markdown)
        self.assertIn("AI 合成的角色模拟", markdown)

    def test_builds_ex_skill_style_behavior_rules_from_target_messages(self):
        profile = build_clone_profile(
            "Target",
            [
                ChatMessage("Me", "我今天有点难过", False, None),
                ChatMessage("Target", "宝宝别难过，我在呢", True, None),
                ChatMessage("Me", "你怎么又不回", False, None),
                ChatMessage("Target", "晚点回你，我在忙，别催", True, None),
                ChatMessage("Target", "你呢？吃了吗？", True, None),
                ChatMessage("Target", "算了不想吵", True, None),
            ],
            clone_id="abc",
        )

        self.assertIn("宝宝", profile.rules.address_terms)
        self.assertTrue(any("安慰" in rule and "我在" in rule for rule in profile.rules.emotional_patterns))
        self.assertTrue(any("冲突" in rule and "不想吵" in rule for rule in profile.rules.emotional_patterns))
        self.assertTrue(any("反问" in rule and "吃了吗" in rule for rule in profile.rules.relationship_behaviors))
        self.assertTrue(any("忙" in rule and "晚点" in rule for rule in profile.rules.boundary_behaviors))

    def test_system_prompt_includes_extracted_behavior_rules(self):
        profile = build_clone_profile(
            "Target",
            [
                ChatMessage("Me", "我今天有点难过", False, None),
                ChatMessage("Target", "宝宝别难过，我在呢", True, None),
                ChatMessage("Target", "晚点回你，我在忙，别催", True, None),
            ],
            clone_id="abc",
        )

        prompt = profile_to_system_prompt(profile)

        self.assertIn("Behavior rules", prompt)
        self.assertIn("宝宝", prompt)
        self.assertIn("晚点", prompt)
