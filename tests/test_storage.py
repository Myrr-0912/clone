import tempfile
import unittest
from pathlib import Path

from cyberclone.models import VoiceTrainingStatus
from cyberclone.storage import CloneStore


class StorageTests(unittest.TestCase):
    def test_creates_clone_with_profile_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: 哈哈哈 我来了",
                voice_filename="voice.wav",
                voice_bytes=b"RIFF",
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "profile" / "persona.md").exists())
            self.assertTrue((clone_dir / "profile" / "rules.md").exists())
            self.assertTrue((clone_dir / "voice" / "voice.wav").exists())
            self.assertEqual(store.load_clone(clone.clone_id).name, "Target")

    def test_persists_extracted_behavior_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="\n".join(
                    [
                        "Me: 我今天有点难过",
                        "Target: 宝宝别难过，我在呢",
                        "Target: 晚点回你，我在忙，别催",
                    ]
                ),
            )

            loaded = store.load_clone(clone.clone_id)
            rules_markdown = (Path(tmp) / clone.clone_id / "profile" / "rules.md").read_text(encoding="utf-8")

            self.assertIn("宝宝", loaded.rules.address_terms)
            self.assertTrue(any("晚点" in rule for rule in loaded.rules.boundary_behaviors))
            self.assertIn("Address Terms", rules_markdown)
            self.assertIn("宝宝", rules_markdown)
            self.assertIn("晚点", rules_markdown)

    def test_saves_optional_sticker_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_filename="voice.wav",
                voice_bytes=b"RIFF",
                sticker_files=[("../fun.gif", b"GIF89a")],
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "stickers" / "fun.gif").exists())
            self.assertEqual(store.load_clone(clone.clone_id).source_stats["sticker_files"], 1)

    def test_saves_multiple_voice_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_files=[
                    ("../voice-a.wav", b"RIFFA"),
                    ("voice-b.wav", b"RIFFB"),
                ],
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "voice" / "voice-a.wav").exists())
            self.assertTrue((clone_dir / "voice" / "voice-b.wav").exists())
            stats = store.load_clone(clone.clone_id).source_stats
            self.assertEqual(stats["voice_files"], 2)

    def test_preserves_duplicate_voice_sample_names_on_create(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_files=[
                    ("sample.wav", b"RIFFA"),
                    ("../sample.wav", b"RIFFB"),
                ],
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertEqual(clone.voice.sample_filenames, ["sample.wav", "sample-2.wav"])
            self.assertEqual((clone_dir / "voice" / "sample.wav").read_bytes(), b"RIFFA")
            self.assertEqual((clone_dir / "voice" / "sample-2.wav").read_bytes(), b"RIFFB")

    def test_saves_optional_local_media_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_filename="",
                voice_bytes=b"",
                image_files=[("../photo.png", b"PNG")],
                video_files=[("../clip.mp4", b"MP4")],
                moments_files=[("../moments.json", b"{}")],
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "images" / "photo.png").exists())
            self.assertTrue((clone_dir / "videos" / "clip.mp4").exists())
            self.assertTrue((clone_dir / "moments" / "moments.json").exists())
            stats = store.load_clone(clone.clone_id).source_stats
            self.assertEqual(stats["image_files"], 1)
            self.assertEqual(stats["video_files"], 1)
            self.assertEqual(stats["moments_files"], 1)

    def test_updates_persisted_voice_training_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_files=[("voice.wav", b"RIFF")],
            )
            status = VoiceTrainingStatus(
                status="error",
                adapter="mock",
                message="training failed",
                sample_filename="voice.wav",
                sample_filenames=["voice.wav"],
                sample_count=1,
                error="backend unavailable",
            )

            store.update_voice_status(clone.clone_id, status)

            self.assertEqual(store.load_voice_status(clone.clone_id).status, "error")
            self.assertEqual(store.load_clone(clone.clone_id).voice.error, "backend unavailable")

    def test_appends_voice_samples_to_existing_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_files=[("first.wav", b"RIFFA")],
            )

            updated = store.add_voice_samples(
                clone.clone_id,
                [
                    ("../second.wav", b"RIFFB"),
                    ("third.webm", b"WEBM"),
                ],
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "voice" / "second.wav").exists())
            self.assertTrue((clone_dir / "voice" / "third.webm").exists())
            self.assertEqual(updated.voice.status, "samples_ready")
            self.assertEqual(updated.voice.sample_filenames, ["first.wav", "second.wav", "third.webm"])
            self.assertEqual(updated.source_stats["voice_files"], 3)
            self.assertEqual(store.load_voice_status(clone.clone_id).sample_count, 3)

    def test_appending_duplicate_voice_sample_name_does_not_overwrite_existing_sample(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: hi",
                voice_files=[("first.wav", b"ORIGINAL")],
            )

            updated = store.add_voice_samples(clone.clone_id, [("../first.wav", b"NEW")])

            clone_dir = Path(tmp) / clone.clone_id
            self.assertEqual(updated.voice.sample_filenames, ["first.wav", "first-2.wav"])
            self.assertEqual((clone_dir / "voice" / "first.wav").read_bytes(), b"ORIGINAL")
            self.assertEqual((clone_dir / "voice" / "first-2.wav").read_bytes(), b"NEW")

    def test_appends_text_correction_to_existing_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: 哈哈哈 我来了",
            )

            updated = store.add_text_correction(clone.clone_id, "不要再说哈哈哈")

            clone_dir = Path(tmp) / clone.clone_id
            self.assertEqual(updated.corrections, ["不要再说哈哈哈"])
            self.assertEqual(store.load_clone(clone.clone_id).corrections, ["不要再说哈哈哈"])
            self.assertIn("不要再说哈哈哈", (clone_dir / "profile" / "corrections.md").read_text(encoding="utf-8"))
            self.assertIn("不要再说哈哈哈", (clone_dir / "profile" / "rules.md").read_text(encoding="utf-8"))
