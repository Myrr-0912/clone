import unittest

from cyberclone.chatlog import parse_chat_log


class ChatLogTests(unittest.TestCase):
    def test_parses_wechat_style_lines(self):
        raw = """2026-01-01 10:00 Alice: 你在干嘛
2026-01-01 10:01 Bob: 刚吃完饭 哈哈哈
2026-01-01 10:02 Bob: 等下去健身"""

        messages = parse_chat_log(raw, target_name="Bob")

        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[1].speaker, "Bob")
        self.assertEqual(messages[1].text, "刚吃完饭 哈哈哈")
        self.assertTrue(messages[1].is_target)

    def test_parses_json_messages(self):
        raw = '[{"sender":"Me","content":"早"},{"sender":"Clone","content":"早啊"}]'

        messages = parse_chat_log(raw, target_name="Clone")

        self.assertEqual([m.text for m in messages], ["早", "早啊"])
        self.assertFalse(messages[0].is_target)
        self.assertTrue(messages[1].is_target)
