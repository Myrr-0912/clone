import base64
import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import cyberclone.auth as auth
from cyberclone.api import paths
from cyberclone.api.main import create_app
from cyberclone.persona import build_clone_profile
from cyberclone.storage import CloneStore


class CloneStoreCrudTests(unittest.TestCase):
    def test_lists_updates_and_deletes_user_clones(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            alice_store = CloneStore(root, user_id="alice")
            bob_store = CloneStore(root, user_id="bob")

            alice_first = alice_store.create_clone(target_name="Alice One", chat_text="Alice One: hello")
            alice_second = alice_store.create_clone(target_name="Alice Two", chat_text="Alice Two: hi")
            bob_clone = bob_store.create_clone(target_name="Bob One", chat_text="Bob One: private")

            self.assertEqual(
                {profile.clone_id for profile in alice_store.list_clones()},
                {alice_first.clone_id, alice_second.clone_id},
            )
            self.assertEqual([profile.clone_id for profile in bob_store.list_clones()], [bob_clone.clone_id])

            updated = alice_store.update_clone(alice_first.clone_id, target_name="Alice Renamed")

            self.assertEqual(updated.name, "Alice Renamed")
            self.assertEqual(alice_store.load_clone(alice_first.clone_id).name, "Alice Renamed")
            self.assertIn(
                "Alice Renamed",
                (
                    root
                    / "users"
                    / "alice"
                    / "clones"
                    / alice_first.clone_id
                    / "profile"
                    / "profile.json"
                ).read_text(encoding="utf-8"),
            )

            self.assertTrue(alice_store.delete_clone(alice_second.clone_id))
            self.assertFalse((root / "users" / "alice" / "clones" / alice_second.clone_id).exists())
            self.assertFalse(alice_store.delete_clone("missing-clone"))
            self.assertEqual([profile.clone_id for profile in bob_store.list_clones()], [bob_clone.clone_id])

    def test_update_existing_clone_rebuilds_text_vector_and_voice_data(self):
        def text_profile_builder(target_name, messages, raw_text):
            profile = build_clone_profile(target_name, messages)
            profile.source_stats["text_training_backend"] = f"builder:{target_name}:{len(messages)}"
            profile.source_stats["raw_text_chars"] = len(raw_text)
            return profile

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = CloneStore(root, user_id="alice", text_profile_builder=text_profile_builder)
            created = store.create_clone(
                target_name="Target",
                chat_text="Target: coffee\nMe: ok",
                voice_files=[("old.wav", b"RIFFOLD")],
            )

            updated = store.update_clone(
                created.clone_id,
                target_name="Target Updated",
                chat_text="Target Updated: tea\nMe: yes",
                voice_files=[("new.wav", b"RIFFNEW")],
            )

            clone_dir = root / "users" / "alice" / "clones" / created.clone_id
            raw_chat = (clone_dir / "raw" / "chat.txt").read_text(encoding="utf-8")
            raw_index = json.loads((clone_dir / "raw" / "chat_messages.json").read_text(encoding="utf-8"))
            vector_manifest = json.loads((clone_dir / "vector" / "manifest.json").read_text(encoding="utf-8"))
            context = store.retrieve_chat_context(created.clone_id, "tea")

            self.assertEqual(updated.clone_id, created.clone_id)
            self.assertEqual(updated.name, "Target Updated")
            self.assertIn("tea", raw_chat)
            self.assertNotIn("coffee", raw_chat)
            self.assertIn("tea", json.dumps(raw_index, ensure_ascii=False))
            self.assertEqual(updated.source_stats["text_training_backend"], "builder:Target Updated:2")
            self.assertEqual(updated.source_stats["voice_files"], 2)
            self.assertGreaterEqual(updated.source_stats["vector_chunk_count"], 1)
            self.assertTrue(Path(updated.source_stats["vector_db_path"]).exists())
            self.assertTrue(vector_manifest["name"].startswith(f"Target Updated-{created.clone_id}"))
            self.assertIn("tea", context)
            self.assertEqual(updated.voice.sample_filenames, ["old.wav", "new.wav"])


class CloneCrudApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self._originals = {
            "data_root": paths.DATA_ROOT,
            "env_path": paths.ENV_PATH,
            "user_store": auth.USER_STORE_PATH,
            "session_store": auth.SESSION_STORE_PATH,
        }
        paths.DATA_ROOT = root / "data"
        paths.ENV_PATH = root / "fake.env"
        auth.USER_STORE_PATH = root / "auth" / "users.json"
        auth.SESSION_STORE_PATH = root / "auth" / "sessions.json"
        self.addCleanup(self._restore)

        self.app = create_app()

    def _restore(self):
        paths.DATA_ROOT = self._originals["data_root"]
        paths.ENV_PATH = self._originals["env_path"]
        auth.USER_STORE_PATH = self._originals["user_store"]
        auth.SESSION_STORE_PATH = self._originals["session_store"]

    def _client(self) -> TestClient:
        client = TestClient(self.app)
        self.addCleanup(client.close)
        return client

    def test_user_can_list_update_use_and_delete_only_own_clones(self):
        alice = self._client()
        bob = self._client()
        alice.post("/api/auth/register", json={"username": "Alice", "password": "s3cret"})
        bob.post("/api/auth/register", json={"username": "Bob", "password": "s3cret"})

        created = alice.post(
            "/api/clones", json={"targetName": "Dad", "chatText": "Dad: coffee"}
        ).json()
        clone_id = created["clone"]["cloneId"]

        listed = alice.get("/api/clones").json()
        bob_listed = bob.get("/api/clones").json()
        self.assertEqual([clone["cloneId"] for clone in listed["clones"]], [clone_id])
        self.assertEqual(listed["clones"][0]["name"], "Dad")
        self.assertEqual(bob_listed["clones"], [])

        renamed = alice.put(
            f"/api/clones/{clone_id}", json={"targetName": "Dad Renamed"}
        ).json()
        self.assertEqual(renamed["clone"]["cloneId"], clone_id)
        self.assertEqual(renamed["clone"]["name"], "Dad Renamed")

        forbidden = bob.get(f"/api/clones/{clone_id}")
        self.assertEqual(forbidden.status_code, 404)

        deleted = alice.delete(f"/api/clones/{clone_id}").json()
        self.assertTrue(deleted["ok"])
        self.assertEqual(alice.get("/api/clones").json()["clones"], [])
        missing = alice.get(f"/api/clones/{clone_id}")
        self.assertEqual(missing.status_code, 404)

    def test_put_existing_clone_updates_training_payload_under_same_clone_id(self):
        alice = self._client()
        registered = alice.post(
            "/api/auth/register", json={"username": "Alice", "password": "s3cret"}
        ).json()
        user_id = registered["user"]["id"]

        created = alice.post(
            "/api/clones", json={"targetName": "Dad", "chatText": "Dad: coffee"}
        ).json()
        clone_id = created["clone"]["cloneId"]

        updated = alice.put(
            f"/api/clones/{clone_id}",
            json={
                "targetName": "Dad Updated",
                "chatText": "Dad Updated: tea\nMe: ok",
                "voiceFiles": [
                    {"name": "sample.wav", "data": base64.b64encode(b"RIFFNEW").decode("ascii")}
                ],
            },
        ).json()

        clone_dir = paths.DATA_ROOT / "users" / user_id / "clones" / clone_id
        raw_chat = (clone_dir / "raw" / "chat.txt").read_text(encoding="utf-8")
        vector_manifest = json.loads(
            (clone_dir / "vector" / "manifest.json").read_text(encoding="utf-8")
        )

        self.assertEqual(updated["clone"]["cloneId"], clone_id)
        self.assertEqual(updated["clone"]["name"], "Dad Updated")
        self.assertIn("tea", raw_chat)
        self.assertNotIn("coffee", raw_chat)
        self.assertEqual(updated["clone"]["sourceStats"]["voice_files"], 1)
        self.assertGreaterEqual(updated["clone"]["sourceStats"]["vector_chunk_count"], 1)
        self.assertTrue(vector_manifest["name"].startswith(f"Dad Updated-{clone_id}"))


if __name__ == "__main__":
    unittest.main()
