import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app.core.security as auth
from app.core import paths
from app.main import create_app


class AuthWebApiTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name)

        self._original_data_root = paths.DATA_ROOT
        self._original_env_path = paths.ENV_PATH
        self._original_user_store = auth.USER_STORE_PATH
        self._original_session_store = auth.SESSION_STORE_PATH

        paths.DATA_ROOT = root / "data"
        paths.ENV_PATH = root / "fake.env"
        auth.USER_STORE_PATH = root / "auth" / "users.json"
        auth.SESSION_STORE_PATH = root / "auth" / "sessions.json"
        self.addCleanup(self._restore)

        self.app = create_app()

    def _restore(self):
        paths.DATA_ROOT = self._original_data_root
        paths.ENV_PATH = self._original_env_path
        auth.USER_STORE_PATH = self._original_user_store
        auth.SESSION_STORE_PATH = self._original_session_store

    def _client(self) -> TestClient:
        client = TestClient(self.app)
        self.addCleanup(client.close)
        return client

    def test_clone_api_requires_login(self):
        client = self._client()
        response = client.post("/api/v1/clones", json={"targetName": "Dad", "chatText": "Dad: hi"})
        self.assertEqual(response.status_code, 401)

    def test_register_creates_session_and_scopes_clone_resources_to_user(self):
        client = self._client()
        registered = client.post(
            "/api/v1/auth/register", json={"username": "Alice", "password": "s3cret"}
        ).json()

        created = client.post(
            "/api/v1/clones", json={"targetName": "Dad", "chatText": "Dad: coffee"}
        ).json()
        clone_id = created["clone"]["cloneId"]
        user_id = registered["user"]["id"]

        user_clone_dir = paths.DATA_ROOT / "users" / user_id / "clones" / clone_id
        self.assertTrue((user_clone_dir / "profile" / "profile.json").exists())
        self.assertTrue((user_clone_dir / "vector" / "db.json").exists())
        self.assertFalse((paths.DATA_ROOT / clone_id).exists())

    def test_admin_endpoint_requires_admin_and_returns_vector_resources(self):
        alice = self._client()
        alice.post("/api/v1/auth/register", json={"username": "Alice", "password": "s3cret"})
        alice.post("/api/v1/clones", json={"targetName": "Dad", "chatText": "Dad: latte"})

        forbidden = alice.get("/api/v1/admin/vector-dbs")
        self.assertEqual(forbidden.status_code, 403)

        auth.register("Root", "admin-pass", role="admin")
        admin = self._client()
        admin.post("/api/v1/auth/login", json={"username": "root", "password": "admin-pass"})

        response = admin.get("/api/v1/admin/vector-dbs")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["vectorDbCount"], 1)
        self.assertGreater(body["totalVectorDbSizeBytes"], 0)
        self.assertEqual(body["resources"][0]["userId"], auth.authenticate("alice", "s3cret")["id"])
        self.assertEqual(body["resources"][0]["cloneName"], "Dad")
        self.assertGreaterEqual(body["resources"][0]["chunkCount"], 1)


if __name__ == "__main__":
    unittest.main()
