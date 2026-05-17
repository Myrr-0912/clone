import json
import tempfile
import unittest
from pathlib import Path

import app.core.security as auth


class AuthTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        root = Path(self.tmpdir.name)
        self.original_user_store_path = auth.USER_STORE_PATH
        self.original_session_store_path = auth.SESSION_STORE_PATH
        auth.USER_STORE_PATH = root / "users.json"
        auth.SESSION_STORE_PATH = root / "sessions.json"
        self.addCleanup(self._restore_paths)

    def _restore_paths(self):
        auth.USER_STORE_PATH = self.original_user_store_path
        auth.SESSION_STORE_PATH = self.original_session_store_path

    def test_register_normalizes_username_and_does_not_store_plaintext_password(self):
        user = auth.register("  Alice  ", "s3cret")

        self.assertEqual(user["username"], "alice")
        self.assertEqual(user["role"], "user")
        self.assertIn("id", user)
        self.assertNotIn("password_hash", user)
        self.assertNotIn("salt", user)

        raw_store = auth.USER_STORE_PATH.read_text(encoding="utf-8")
        stored = json.loads(raw_store)["users"][0]
        self.assertEqual(stored["username"], "alice")
        self.assertIn("password_hash", stored)
        self.assertIn("salt", stored)
        self.assertNotIn("s3cret", raw_store)

    def test_register_rejects_duplicate_normalized_username(self):
        auth.register("Alice", "first-password")

        with self.assertRaises(ValueError):
            auth.register("  ALICE  ", "second-password")

    def test_authenticate_accepts_correct_password_and_rejects_wrong_password(self):
        registered = auth.register("alice", "s3cret")

        authenticated = auth.authenticate(" ALICE ", "s3cret")

        self.assertEqual(authenticated, registered)
        self.assertIsNone(auth.authenticate("alice", "wrong-password"))
        self.assertIsNone(auth.authenticate("missing", "s3cret"))

    def test_create_get_and_delete_session(self):
        user = auth.register("alice", "s3cret")

        token = auth.create_session(user["id"])
        session = auth.get_session(token)

        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)
        self.assertEqual(session["token"], token)
        self.assertEqual(session["user_id"], user["id"])
        self.assertEqual(session["user"], user)

        self.assertTrue(auth.delete_session(token))
        self.assertIsNone(auth.get_session(token))
        self.assertFalse(auth.delete_session(token))

    def test_role_is_saved_and_returned_for_admin_user(self):
        registered = auth.register("Root", "s3cret", role="admin")

        self.assertEqual(registered["role"], "admin")
        self.assertEqual(auth.authenticate("root", "s3cret")["role"], "admin")

        stored = json.loads(auth.USER_STORE_PATH.read_text(encoding="utf-8"))["users"][0]
        self.assertEqual(stored["role"], "admin")

    def test_ensure_default_admin_creates_admin_with_admin_password(self):
        user = auth.ensure_default_admin()

        self.assertEqual(user["username"], "admin")
        self.assertEqual(user["role"], "admin")
        self.assertEqual(auth.authenticate("admin", "admin"), user)

        raw_store = auth.USER_STORE_PATH.read_text(encoding="utf-8")
        self.assertNotIn('"password": "admin"', raw_store)
        self.assertNotIn("adminadmin", raw_store)

        second = auth.ensure_default_admin()
        stored = json.loads(auth.USER_STORE_PATH.read_text(encoding="utf-8"))["users"]
        self.assertEqual(second["id"], user["id"])
        self.assertEqual(len(stored), 1)

    def test_ensure_default_admin_promotes_existing_admin_username(self):
        existing = auth.register("admin", "old-password", role="user")

        ensured = auth.ensure_default_admin()

        self.assertEqual(ensured["id"], existing["id"])
        self.assertEqual(ensured["role"], "admin")
        self.assertEqual(auth.authenticate("admin", "admin"), ensured)


if __name__ == "__main__":
    unittest.main()
