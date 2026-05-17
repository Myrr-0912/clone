import tempfile
import unittest
from pathlib import Path

from cyberclone.chatlog import ChatMessage
from cyberclone.llm import DeepSeekChatEngine, LLMSettings
from cyberclone.models import CloneMemory, CloneProfile, CloneStyle
from cyberclone.rag import build_chat_index, format_retrieved_context, retrieve_relevant_messages
from cyberclone.storage import CloneStore


class RagTests(unittest.TestCase):
    def test_retrieves_relevant_real_chat_messages_for_query(self):
        records = build_chat_index(
            [
                ChatMessage("Me", "你今天吃什么", False, "2026-01-01 10:00"),
                ChatMessage("Target", "随便吃点吧", True, "2026-01-01 10:01"),
                ChatMessage("Me", "还记得那个健身房吗", False, "2026-01-02 20:00"),
                ChatMessage("Target", "当然啊 健身房出来还去买了冰美式 哈哈哈", True, "2026-01-02 20:01"),
            ]
        )

        snippets = retrieve_relevant_messages(records, "健身房那次你还记得吗", max_snippets=2)

        self.assertEqual(len(snippets), 2)
        self.assertIn("健身房", snippets[0].text)
        self.assertTrue(any("冰美式" in snippet.text for snippet in snippets))

    def test_formats_retrieved_context_for_llm_prompt(self):
        records = build_chat_index(
            [
                ChatMessage("Me", "你还记得健身房吗", False, "2026-01-02 20:00"),
                ChatMessage("Target", "当然啊 健身房出来还去买了冰美式 哈哈哈", True, "2026-01-02 20:01"),
            ]
        )
        snippets = retrieve_relevant_messages(records, "健身房", max_snippets=2)

        context = format_retrieved_context(snippets)

        self.assertIn("Retrieved Chat Evidence", context)
        self.assertIn("TARGET", context)
        self.assertIn("冰美式", context)
        self.assertIn("不要编造", context)

    def test_store_persists_chat_index_and_retrieves_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="\n".join(
                    [
                        "Me: 还记得健身房吗",
                        "Target: 当然啊 健身房出来还去买了冰美式 哈哈哈",
                    ]
                ),
            )

            context = store.retrieve_chat_context(clone.clone_id, "健身房那次")

            self.assertTrue((Path(tmp) / clone.clone_id / "raw" / "chat_messages.json").exists())
            self.assertIn("Retrieved Chat Evidence", context)
            self.assertIn("冰美式", context)

    def test_store_backfills_missing_chat_index_from_raw_chat_for_existing_clones(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="\n".join(
                    [
                        "Me: 还记得健身房吗",
                        "Target: 当然啊 健身房出来还去买了冰美式 哈哈哈",
                    ]
                ),
            )
            index_path = Path(tmp) / clone.clone_id / "raw" / "chat_messages.json"
            index_path.unlink()

            context = store.retrieve_chat_context(clone.clone_id, "健身房那次")

            self.assertTrue(index_path.exists())
            self.assertIn("冰美式", context)

    def test_deepseek_engine_includes_retrieved_context_when_present(self):
        calls = []

        def fake_transport(url, headers, payload, timeout):
            calls.append(payload)
            return {"choices": [{"message": {"content": "记得啊，健身房出来还买了冰美式"}}]}

        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["哈哈哈"], average_length=10),
            memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身。"),
        )
        context = "## Retrieved Chat Evidence\n- TARGET Target: 健身房出来还去买了冰美式 哈哈哈"

        reply = DeepSeekChatEngine(
            LLMSettings(api_key="sk-test"),
            transport=fake_transport,
        ).reply(profile, "健身房那次你还记得吗", retrieved_context=context)

        self.assertIn("冰美式", reply.text)
        self.assertIn("Retrieved Chat Evidence", calls[0]["messages"][0]["content"])
        self.assertIn("冰美式", calls[0]["messages"][0]["content"])
