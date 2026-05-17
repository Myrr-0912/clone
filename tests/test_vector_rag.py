import sys
import types
import unittest

from cyberclone.chatlog import ChatMessage
from cyberclone.vector_rag import (
    build_chunks_from_messages,
    format_vector_evidence,
    index_clone_messages,
    retrieve_clone_evidence,
)


class VectorRagTests(unittest.TestCase):
    def test_builds_context_windows_with_boundary_metadata(self):
        messages = [
            ChatMessage("Me", "first question", False, "2026-01-01 10:00"),
            ChatMessage("Target", "target answer", True, "2026-01-01 10:01"),
            ChatMessage("Me", "follow up", False, "2026-01-01 10:02"),
            ChatMessage("Other", "   ", False, "2026-01-01 10:03"),
        ]

        chunks = build_chunks_from_messages(
            messages,
            user_id="user-1",
            clone_id="clone-1",
            target_name="Target",
        )

        self.assertEqual(len(chunks), 3)
        self.assertIn("first question", chunks[0]["text"])
        self.assertIn("target answer", chunks[0]["text"])
        self.assertNotIn("follow up", chunks[0]["text"])
        self.assertIn("first question", chunks[1]["text"])
        self.assertIn("target answer", chunks[1]["text"])
        self.assertIn("follow up", chunks[1]["text"])
        self.assertNotIn("first question", chunks[2]["text"])
        self.assertIn("target answer", chunks[2]["text"])
        self.assertIn("follow up", chunks[2]["text"])

        self.assertEqual(chunks[0]["metadata"]["speakers"], ["Me", "Target"])
        self.assertEqual(chunks[0]["metadata"]["ordinals"], [0, 1])
        self.assertTrue(chunks[0]["metadata"]["contains_target"])
        self.assertEqual(chunks[1]["metadata"]["speakers"], ["Me", "Target", "Me"])
        self.assertEqual(chunks[1]["metadata"]["ordinals"], [0, 1, 2])
        self.assertEqual(chunks[2]["metadata"]["speakers"], ["Target", "Me"])
        self.assertEqual(chunks[2]["metadata"]["ordinals"], [1, 2])
        self.assertEqual(chunks[1]["metadata"]["user_id"], "user-1")
        self.assertEqual(chunks[1]["metadata"]["clone_id"], "clone-1")

    def test_format_vector_evidence_includes_title_grounding_and_results(self):
        evidence = format_vector_evidence(
            [
                {
                    "text": "Target: remembered coffee",
                    "score": 0.91,
                    "metadata": {
                        "speakers": ["Target"],
                        "ordinals": [4],
                        "contains_target": True,
                    },
                },
                {
                    "content": "Me: asked about the gym",
                    "metadata": {"speakers": ["Me"], "ordinals": [3]},
                },
            ]
        )

        self.assertIn("Retrieved Vector Evidence", evidence)
        self.assertIn("do not invent", evidence.casefold())
        self.assertIn("Target", evidence)
        self.assertIn("ordinal 4", evidence)
        self.assertIn("remembered coffee", evidence)
        self.assertIn("asked about the gym", evidence)

    def test_index_clone_messages_passes_chunks_to_vector_store(self):
        calls = []

        fake_vector_store = types.ModuleType("cyberclone.vector_store")

        def index_chunks(db_path, chunks):
            calls.append({"db_path": db_path, "chunks": chunks})
            return {"indexed": len(chunks)}

        fake_vector_store.index_chunks = index_chunks

        with _temporary_vector_store(fake_vector_store):
            result = index_clone_messages(
                db_path="vectors.db",
                user_id="user-1",
                clone_id="clone-1",
                messages=[ChatMessage("Target", "hello there", True)],
                target_name="Target",
            )

        self.assertEqual(result, {"indexed": 1})
        self.assertEqual(calls[0]["db_path"], "vectors.db")
        self.assertEqual(calls[0]["chunks"][0]["metadata"]["user_id"], "user-1")
        self.assertEqual(calls[0]["chunks"][0]["metadata"]["clone_id"], "clone-1")
        self.assertTrue(calls[0]["chunks"][0]["metadata"]["contains_target"])

    def test_retrieve_clone_evidence_passes_scope_to_vector_store(self):
        calls = []
        fake_vector_store = types.ModuleType("cyberclone.vector_store")

        def search_chunks(db_path, **kwargs):
            calls.append({"db_path": db_path, "kwargs": kwargs})
            return [
                {
                    "text": "Target: this came from scoped vector search",
                    "metadata": {"speakers": ["Target"], "ordinals": [7]},
                }
            ]

        fake_vector_store.search_chunks = search_chunks

        with _temporary_vector_store(fake_vector_store):
            evidence = retrieve_clone_evidence(
                db_path="vectors.db",
                user_id="user-1",
                clone_id="clone-1",
                query="what did target say?",
                top_k=3,
            )

        self.assertEqual(calls[0]["db_path"], "vectors.db")
        self.assertEqual(
            calls[0]["kwargs"],
            {
                "user_id": "user-1",
                "clone_id": "clone-1",
                "query": "what did target say?",
                "top_k": 3,
            },
        )
        self.assertIn("Retrieved Vector Evidence", evidence)
        self.assertIn("scoped vector search", evidence)


class _temporary_vector_store:
    def __init__(self, fake_module):
        self.fake_module = fake_module
        self.original = None

    def __enter__(self):
        self.original = sys.modules.get("cyberclone.vector_store")
        sys.modules["cyberclone.vector_store"] = self.fake_module
        return self.fake_module

    def __exit__(self, exc_type, exc, tb):
        if self.original is None:
            sys.modules.pop("cyberclone.vector_store", None)
        else:
            sys.modules["cyberclone.vector_store"] = self.original


if __name__ == "__main__":
    unittest.main()
