import tempfile
import unittest
from pathlib import Path

from app.services.resource_layout import clone_paths, ensure_clone_layout


class ResourceLayoutTests(unittest.TestCase):
    def test_same_clone_id_is_isolated_by_user(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            alice = ensure_clone_layout(root, "alice", "shared-clone")
            bob = ensure_clone_layout(root, "bob", "shared-clone")

            self.assertNotEqual(alice.clone_dir, bob.clone_dir)
            self.assertEqual(alice.clone_dir, root / "users" / "alice" / "clones" / "shared-clone")
            self.assertEqual(bob.clone_dir, root / "users" / "bob" / "clones" / "shared-clone")

    def test_malicious_user_and_clone_ids_are_confined_to_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            paths = ensure_clone_layout(root, "../evil/user", "..\\outside:clone")

            self.assertEqual(paths.clone_dir, root / "users" / "evil-user" / "clones" / "outside-clone")
            self.assertTrue(paths.clone_dir.is_relative_to(root))
            self.assertNotIn("..", paths.clone_dir.parts)

    def test_unicode_segments_are_preserved_when_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            paths = clone_paths(root, "用户 一", "克隆 一")

            self.assertEqual(paths.user_dir, root / "users" / "用户_一")
            self.assertEqual(paths.clone_dir, root / "users" / "用户_一" / "clones" / "克隆_一")

    def test_ensure_clone_layout_creates_expected_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths = ensure_clone_layout(Path(tmp), "user-1", "clone-1")

            self.assertTrue(paths.profile_dir.is_dir())
            self.assertTrue(paths.raw_dir.is_dir())
            self.assertTrue(paths.vector_dir.is_dir())
            self.assertTrue(paths.voice_samples_dir.is_dir())
            self.assertTrue(paths.voice_artifacts_dir.is_dir())

    def test_clone_paths_is_stable_and_does_not_create_directories(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            first = clone_paths(root, "User 1", "Clone 1")
            second = clone_paths(root, "User 1", "Clone 1")

            self.assertEqual(first, second)
            self.assertEqual(first.user_dir, root / "users" / "User_1")
            self.assertEqual(first.clone_dir, root / "users" / "User_1" / "clones" / "Clone_1")
            self.assertEqual(first.profile_dir, first.clone_dir / "profile")
            self.assertEqual(first.raw_dir, first.clone_dir / "raw")
            self.assertEqual(first.vector_dir, first.clone_dir / "vector")
            self.assertEqual(first.vector_db_path, first.vector_dir / "db.json")
            self.assertEqual(first.vector_manifest_path, first.vector_dir / "manifest.json")
            self.assertEqual(first.voice_samples_dir, first.clone_dir / "voice" / "samples")
            self.assertEqual(first.voice_model_manifest_path, first.clone_dir / "voice" / "model" / "manifest.json")
            self.assertEqual(first.voice_artifacts_dir, first.clone_dir / "voice" / "model" / "artifacts")
            self.assertFalse(first.clone_dir.exists())


if __name__ == "__main__":
    unittest.main()
