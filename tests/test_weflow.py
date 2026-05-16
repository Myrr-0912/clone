import unittest

from cyberclone.weflow import WeFlowClient, chatlab_to_training_text


class WeFlowTests(unittest.TestCase):
    def test_lists_chatlab_sessions_with_token_header(self):
        calls = []

        def fake_request(path, params, headers):
            calls.append((path, params, headers))
            return {
                "sessions": [
                    {
                        "id": "wxid_target",
                        "name": "Target",
                        "platform": "wechat",
                        "type": "private",
                        "messageCount": 42,
                        "lastMessageAt": 1738713600,
                    }
                ]
            }

        client = WeFlowClient(base_url="http://127.0.0.1:5031", token="secret", request_json=fake_request)
        sessions = client.list_sessions(keyword="Tar", limit=20)

        self.assertEqual(sessions[0].session_id, "wxid_target")
        self.assertEqual(sessions[0].name, "Target")
        self.assertEqual(calls[0][0], "/api/v1/sessions")
        self.assertEqual(calls[0][1]["format"], "chatlab")
        self.assertEqual(calls[0][2]["Authorization"], "Bearer secret")

    def test_converts_chatlab_messages_to_training_text(self):
        payload = {
            "messages": [
                {"sender": "wxid_a", "accountName": "Target", "timestamp": 1738713600, "content": "你好"},
                {"sender": "wxid_me", "accountName": "Me", "timestamp": 1738713660, "content": "吃了吗"},
                {"sender": "wxid_a", "groupNickname": "群昵称", "content": ""},
            ]
        }

        chat_text = chatlab_to_training_text(payload)

        self.assertIn("2025-02-05 00:00 Target: 你好", chat_text)
        self.assertIn("2025-02-05 00:01 Me: 吃了吗", chat_text)
        self.assertNotIn("群昵称", chat_text)

    def test_pulls_session_messages_as_training_text(self):
        def fake_request(path, params, headers):
            self.assertEqual(path, "/api/v1/sessions/wxid_target/messages")
            self.assertEqual(params["limit"], "5000")
            return {"messages": [{"accountName": "Target", "content": "哈哈哈"}], "sync": {"hasMore": False}}

        client = WeFlowClient(base_url="http://127.0.0.1:5031", token="", request_json=fake_request)

        self.assertEqual(client.pull_session_training_text("wxid_target"), "Target: 哈哈哈")
