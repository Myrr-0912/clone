import json
import tempfile
import unittest
from pathlib import Path

from cyberclone.admin_stats import list_clone_resource_stats


class AdminStatsTests(unittest.TestCase):
    def test_lists_clone_resources_across_users_with_duplicate_clone_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            users_root = Path(tmp) / "data" / "users"
            alice_clone = users_root / "alice" / "clones" / "shared-clone"
            bob_clone = users_root / "bob" / "clones" / "shared-clone"

            _write_profile(alice_clone, "Alice Target")
            _write_vector_db(
                alice_clone,
                name="alice-vector-db",
                chunks=7,
                files={"index.bin": b"abc", "meta.json": b"{}"},
            )
            _write_voice_status(
                alice_clone,
                {
                    "status": "ready",
                    "sample_count": 2,
                    "sample_filenames": ["a.wav", "b.wav"],
                    "modelPath": "model/voice.bin",
                },
            )
            (alice_clone / "voice" / "model").mkdir(parents=True)
            (alice_clone / "voice" / "model" / "voice.bin").write_bytes(b"12345")

            _write_profile(bob_clone, "Bob Target")
            _write_vector_db(
                bob_clone,
                name="bob-vector-db",
                chunks=3,
                files={"index.bin": b"longer"},
            )
            (bob_clone / "voice").mkdir(parents=True)
            (bob_clone / "voice" / "sample.wav").write_bytes(b"RIFF")

            stats = list_clone_resource_stats(users_root)

            self.assertEqual(
                [(item["userId"], item["cloneId"]) for item in stats],
                [("alice", "shared-clone"), ("bob", "shared-clone")],
            )
            alice = stats[0]
            bob = stats[1]

            self.assertEqual(alice["cloneName"], "Alice Target")
            self.assertEqual(alice["vectorDbName"], "alice-vector-db")
            self.assertEqual(alice["vectorChunkCount"], 7)
            self.assertEqual(alice["vectorDbSizeBytes"], 5)
            self.assertEqual(alice["voiceStatus"], "ready")
            self.assertEqual(alice["voiceSampleCount"], 2)
            self.assertEqual(alice["voiceModelSizeBytes"], 5)
            self.assertTrue(alice["updatedAt"].endswith("Z"))

            self.assertEqual(bob["cloneName"], "Bob Target")
            self.assertEqual(bob["vectorDbName"], "bob-vector-db")
            self.assertEqual(bob["vectorChunkCount"], 3)
            self.assertEqual(bob["vectorDbSizeBytes"], 6)
            self.assertEqual(bob["voiceStatus"], "samples_ready")
            self.assertEqual(bob["voiceSampleCount"], 1)
            self.assertEqual(bob["voiceModelSizeBytes"], 0)

    def test_returns_defaults_when_profile_manifest_or_resource_dirs_are_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            users_root = Path(tmp) / "data" / "users"
            clone_dir = users_root / "user-1" / "clones" / "empty-clone"
            clone_dir.mkdir(parents=True)

            stats = list_clone_resource_stats(users_root)

            self.assertEqual(len(stats), 1)
            self.assertEqual(
                stats[0],
                {
                    "userId": "user-1",
                    "cloneId": "empty-clone",
                    "cloneName": "empty-clone",
                    "vectorDbName": "",
                    "vectorDbSizeBytes": 0,
                    "vectorChunkCount": 0,
                    "voiceStatus": "missing",
                    "voiceSampleCount": 0,
                    "voiceModelSizeBytes": 0,
                    "updatedAt": stats[0]["updatedAt"],
                },
            )
            self.assertTrue(stats[0]["updatedAt"].endswith("Z"))

    def test_reads_legacy_profile_name_and_counts_size_without_private_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            users_root = Path(tmp) / "data" / "users"
            clone_dir = users_root / "user-1" / "clones" / "clone-1"
            (clone_dir / "profile").mkdir(parents=True)
            (clone_dir / "profile" / "profile.json").write_text(
                json.dumps({"name": "Legacy Profile Name"}),
                encoding="utf-8",
            )
            _write_vector_db(
                clone_dir,
                name="privacy-check",
                chunks=2,
                files={"index.bin": b"vector-bytes"},
            )
            (clone_dir / "raw").mkdir()
            (clone_dir / "raw" / "chat.txt").write_text("private chat body", encoding="utf-8")
            (clone_dir / "voice").mkdir()
            (clone_dir / "voice" / "sample.wav").write_bytes(b"private-audio")

            stats = list_clone_resource_stats(users_root)

            self.assertEqual(stats[0]["cloneName"], "Legacy Profile Name")
            self.assertEqual(stats[0]["vectorDbSizeBytes"], len(b"vector-bytes"))
            self.assertEqual(stats[0]["voiceSampleCount"], 1)
            self.assertNotIn("private chat body", json.dumps(stats, ensure_ascii=False))
            self.assertNotIn("private-audio", json.dumps(stats, ensure_ascii=False))


def _write_profile(clone_dir: Path, clone_name: str) -> None:
    (clone_dir / "profile").mkdir(parents=True)
    (clone_dir / "profile" / "profile.json").write_text(
        json.dumps({"cloneName": clone_name}),
        encoding="utf-8",
    )


def _write_vector_db(clone_dir: Path, name: str, chunks: int, files: dict[str, bytes]) -> None:
    vector_dir = clone_dir / "vector"
    db_dir = vector_dir / "db"
    db_dir.mkdir(parents=True)
    (vector_dir / "manifest.json").write_text(
        json.dumps({"name": name, "chunkCount": chunks, "dbPath": "db"}),
        encoding="utf-8",
    )
    for filename, content in files.items():
        (db_dir / filename).write_bytes(content)


def _write_voice_status(clone_dir: Path, payload: dict[str, object]) -> None:
    voice_dir = clone_dir / "voice"
    voice_dir.mkdir(parents=True)
    (voice_dir / "status.json").write_text(json.dumps(payload), encoding="utf-8")
