import tempfile
import unittest
from pathlib import Path

from cyberclone.models import ChatMessage
from cyberclone.vector_store import (
    MAX_CHARS_PER_CHUNK,
    build_hash_embedding,
    cosine_similarity,
    create_or_replace_index,
    search,
    stats,
)


class VectorStoreTests(unittest.TestCase):
    def test_hash_embedding_and_search_find_relevant_chunk(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "clone.sqlite3"
            create_or_replace_index(
                db_path,
                user_id="user-a",
                clone_id="clone-a",
                chunks=[
                    "coffee latte foam cafe ritual",
                    "espresso beans and morning coffee",
                    "favorite mug with latte art",
                ],
            )

            results = search(db_path, "user-a", "clone-a", "latte coffee cafe", top_k=1)

            self.assertEqual(len(results), 1)
            self.assertIn("coffee", results[0]["text"])
            self.assertGreater(results[0]["score"], 0.0)
            self.assertEqual(results[0]["metadata"]["source_count"], 3)

        embedding = build_hash_embedding("latte coffee cafe", dimensions=16)
        self.assertEqual(len(embedding), 16)
        self.assertAlmostEqual(cosine_similarity(embedding, embedding), 1.0)

    def test_search_filters_by_user_and_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "shared.sqlite3"
            create_or_replace_index(
                db_path,
                "user-a",
                "clone-a",
                ["ordinary picnic notes", "sunny park blanket", "lemon tea"],
            )
            create_or_replace_index(
                db_path,
                "user-b",
                "clone-a",
                ["secret project atlas", "atlas launch phrase", "private atlas notes"],
            )
            create_or_replace_index(
                db_path,
                "user-a",
                "clone-b",
                ["secret project atlas", "atlas launch phrase", "private atlas notes"],
            )

            isolated = search(db_path, "user-a", "clone-a", "secret atlas", top_k=5)
            other_user = search(db_path, "user-b", "clone-a", "secret atlas", top_k=5)
            other_clone = search(db_path, "user-a", "clone-b", "secret atlas", top_k=5)

            self.assertEqual(isolated, [])
            self.assertEqual(len(other_user), 1)
            self.assertIn("secret project atlas", other_user[0]["text"])
            self.assertEqual(len(other_clone), 1)
            self.assertIn("secret project atlas", other_clone[0]["text"])

    def test_stats_report_chunk_count_size_and_updated_at(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "stats.sqlite3"
            create_or_replace_index(
                db_path,
                "user-a",
                "clone-a",
                [
                    ChatMessage("Me", "one coffee memory", False, "2026-01-01 10:00"),
                    ChatMessage("Target", "two latte memory", True, "2026-01-01 10:01"),
                    ChatMessage("Me", "three cafe memory", False, "2026-01-01 10:02"),
                    ChatMessage("Target", "four espresso memory", True, "2026-01-01 10:03"),
                    ChatMessage("Me", "five beans memory", False, "2026-01-01 10:04"),
                    ChatMessage("Target", "six mug memory", True, "2026-01-01 10:05"),
                    ChatMessage("Me", "seven pastry memory", False, "2026-01-01 10:06"),
                ],
            )

            summary = stats(db_path)

            self.assertEqual(summary["chunk_count"], 2)
            self.assertGreater(summary["db_size_bytes"], 0)
            self.assertIsInstance(summary["updated_at"], str)
            self.assertTrue(summary["updated_at"])

    def test_long_text_fragments_split_on_max_chars(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "long.sqlite3"
            filler_size = (MAX_CHARS_PER_CHUNK // 2) + 100
            create_or_replace_index(
                db_path,
                "user-a",
                "clone-a",
                [
                    "coffee " + ("a" * filler_size),
                    "latte " + ("b" * filler_size),
                    "espresso " + ("c" * filler_size),
                ],
            )

            self.assertEqual(stats(db_path)["chunk_count"], 3)

    def test_rebuilding_index_removes_old_chunks_for_same_user_and_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "replace.sqlite3"
            create_or_replace_index(
                db_path,
                "user-a",
                "clone-a",
                ["ancient castle dragon", "stone tower dragon", "old moat dragon"],
            )
            self.assertEqual(len(search(db_path, "user-a", "clone-a", "dragon castle", top_k=3)), 1)

            create_or_replace_index(
                db_path,
                "user-a",
                "clone-a",
                ["modern robotics lab", "sensor array robot", "servo calibration robot"],
            )

            self.assertEqual(search(db_path, "user-a", "clone-a", "dragon castle", top_k=3), [])
            new_results = search(db_path, "user-a", "clone-a", "robot sensor", top_k=3)
            self.assertEqual(len(new_results), 1)
            self.assertIn("modern robotics lab", new_results[0]["text"])
            self.assertEqual(stats(db_path)["chunk_count"], 1)


if __name__ == "__main__":
    unittest.main()
