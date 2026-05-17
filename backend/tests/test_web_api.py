import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

import app.core.security as auth
from app.core import paths
from app.schemas.conversions import (
    decode_speech_payload,
    decode_upload_payload,
    decode_voice_samples_payload,
)
from app.main import create_app
from app.models.clone import VoiceTrainingStatus
from app.services.storage import CloneStore


class WebApiTests(unittest.TestCase):
    """单元测试：纯 payload 解码逻辑（与 HTTP 层无关）。"""

    def test_decodes_voice_data_url_payload(self):
        payload = {
            "targetName": "Target",
            "chatText": "Target: 哈哈哈",
            "voiceName": "voice.wav",
            "voiceData": "data:audio/wav;base64,UklGRg==",
        }
        decoded = decode_upload_payload(payload)
        self.assertEqual(decoded.target_name, "Target")
        self.assertEqual(decoded.voice_filename, "voice.wav")
        self.assertEqual(decoded.voice_bytes, b"RIFF")

    def test_decodes_batch_voice_files_payload(self):
        payload = {
            "targetName": "Target",
            "chatText": "Target: hi",
            "voiceFiles": [
                {"name": "../voice-a.wav", "data": "data:audio/wav;base64,UklGRkE="},
                {"name": "voice-b.wav", "data": "UklGRkI="},
            ],
        }
        decoded = decode_upload_payload(payload)
        self.assertEqual([file.filename for file in decoded.voice_files], ["voice-a.wav", "voice-b.wav"])
        self.assertEqual([file.bytes for file in decoded.voice_files], [b"RIFFA", b"RIFFB"])

    def test_decodes_optional_sticker_files(self):
        payload = {
            "targetName": "Target",
            "chatText": "Target: hi",
            "voiceName": "voice.wav",
            "voiceData": "UklGRg==",
            "stickerFiles": [
                {"name": "../fun.gif", "data": "data:image/gif;base64,R0lGODlh"},
            ],
        }
        decoded = decode_upload_payload(payload)
        self.assertEqual(len(decoded.sticker_files), 1)
        self.assertEqual(decoded.sticker_files[0].filename, "fun.gif")
        self.assertEqual(decoded.sticker_files[0].bytes, b"GIF89a")

    def test_decodes_optional_local_media_files(self):
        payload = {
            "targetName": "Target",
            "chatText": "Target: hi",
            "imageFiles": [{"name": "../photo.png", "data": "iVBORw=="}],
            "videoFiles": [{"name": "../clip.mp4", "data": "AAAA"}],
            "momentsFiles": [{"name": "../moments.json", "data": "e30="}],
        }
        decoded = decode_upload_payload(payload)
        self.assertEqual(decoded.image_files[0].filename, "photo.png")
        self.assertEqual(decoded.video_files[0].filename, "clip.mp4")
        self.assertEqual(decoded.moments_files[0].filename, "moments.json")

    def test_allows_payload_without_voice_sample(self):
        payload = {"targetName": "Target", "chatText": "Target: hi"}
        decoded = decode_upload_payload(payload)
        self.assertEqual(decoded.voice_filename, "")
        self.assertEqual(decoded.voice_bytes, b"")
        self.assertEqual(decoded.voice_files, [])

    def test_rejects_missing_chat_text(self):
        with self.assertRaises(ValueError):
            decode_upload_payload({"targetName": "Target", "voiceName": "voice.wav", "voiceData": "AA=="})

    def test_decodes_speech_payload_with_default_emotion(self):
        decoded = decode_speech_payload({"text": "你好"})
        self.assertEqual(decoded.text, "你好")
        self.assertEqual(decoded.emotion, "natural")
        self.assertIsNone(decoded.inference_steps)
        self.assertIsNone(decoded.cfg_value)

    def test_decodes_speech_payload_with_voice_generation_parameters(self):
        decoded = decode_speech_payload(
            {"text": "你好", "emotion": "warm", "inferenceSteps": 9, "cfgValue": 2.7}
        )
        self.assertEqual(decoded.text, "你好")
        self.assertEqual(decoded.emotion, "warm")
        self.assertEqual(decoded.inference_steps, 9)
        self.assertEqual(decoded.cfg_value, 2.7)

    def test_rejects_speech_payload_without_text(self):
        with self.assertRaises(ValueError):
            decode_speech_payload({"emotion": "warm"})

    def test_decodes_voice_samples_payload_without_requiring_chat_text(self):
        decoded = decode_voice_samples_payload(
            {
                "voiceFiles": [
                    {"name": "../new-a.wav", "data": "UklGRkE="},
                    {"name": "new-b.webm", "data": "data:audio/webm;base64,V0VCTQ=="},
                ]
            }
        )
        self.assertEqual([file.filename for file in decoded], ["new-a.wav", "new-b.webm"])
        self.assertEqual([file.bytes for file in decoded], [b"RIFFA", b"WEBM"])

    def test_rejects_empty_voice_samples_payload(self):
        with self.assertRaises(ValueError):
            decode_voice_samples_payload({"voiceFiles": []})


class WebApiIntegrationTests(unittest.TestCase):
    """集成测试：通过 FastAPI TestClient 访问完整路由。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self._patch_paths(Path(self._tmp.name))
        self.client_factory = TestClient

    def _patch_paths(self, root: Path) -> None:
        from app.api.v1 import voice as voice_router

        self._originals = {
            "data_root": paths.DATA_ROOT,
            "env_path": paths.ENV_PATH,
            "user_store": auth.USER_STORE_PATH,
            "session_store": auth.SESSION_STORE_PATH,
            "refresh_voice": voice_router.voice_module.refresh_voice_training_status,
        }
        paths.DATA_ROOT = root / "data"
        paths.ENV_PATH = root / "fake.env"
        auth.USER_STORE_PATH = root / "auth" / "users.json"
        auth.SESSION_STORE_PATH = root / "auth" / "sessions.json"
        self.addCleanup(self._restore)

    def _restore(self) -> None:
        from app.api.v1 import voice as voice_router

        paths.DATA_ROOT = self._originals["data_root"]
        paths.ENV_PATH = self._originals["env_path"]
        auth.USER_STORE_PATH = self._originals["user_store"]
        auth.SESSION_STORE_PATH = self._originals["session_store"]
        voice_router.voice_module.refresh_voice_training_status = self._originals["refresh_voice"]

    def _build_client(self, refresh_voice_training_status=None) -> TestClient:
        if refresh_voice_training_status is not None:
            from app.api.v1 import voice as voice_router

            voice_router.voice_module.refresh_voice_training_status = (
                refresh_voice_training_status
            )
        app = create_app()
        client = self.client_factory(app)
        self.addCleanup(client.close)
        return client

    def _register(self, client: TestClient, username: str = "alice", password: str = "s3cret") -> dict:
        response = client.post("/api/v1/auth/register", json={"username": username, "password": password})
        response.raise_for_status()
        return response.json()["user"]

    def test_get_voice_status_returns_persisted_training_status(self):
        client = self._build_client(
            refresh_voice_training_status=lambda profile, current, env_path=None: current
        )
        user = self._register(client)
        store = CloneStore(paths.DATA_ROOT, user_id=user["id"])
        profile = store.create_clone(
            target_name="Target",
            chat_text="Target: hi",
            voice_files=[("first.wav", b"RIFF")],
        )
        store.update_voice_status(
            profile.clone_id,
            VoiceTrainingStatus(
                status="queued",
                adapter="http",
                message="training queued",
                sample_filename="first.wav",
                sample_filenames=["first.wav"],
                sample_count=1,
                job_id="job-123",
            ),
        )

        response = client.get(f"/api/v1/clones/{profile.clone_id}/voice/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["voice"]["status"], "queued")
        self.assertEqual(body["voice"]["job_id"], "job-123")
        self.assertEqual(body["clone"]["cloneId"], profile.clone_id)

    def test_get_voice_status_refreshes_and_persists_external_training_status(self):
        def fake_refresh(profile, current, env_path=None):
            return VoiceTrainingStatus(
                status="ready",
                adapter=current.adapter,
                message="voice model ready",
                sample_filename=current.sample_filename,
                sample_filenames=current.sample_filenames,
                sample_count=current.sample_count,
                model_id="voice-model-123",
                job_id=current.job_id,
            )

        client = self._build_client(refresh_voice_training_status=fake_refresh)
        user = self._register(client)
        store = CloneStore(paths.DATA_ROOT, user_id=user["id"])
        profile = store.create_clone(
            target_name="Target",
            chat_text="Target: hi",
            voice_files=[("first.wav", b"RIFF")],
        )
        store.update_voice_status(
            profile.clone_id,
            VoiceTrainingStatus(
                status="queued",
                adapter="http",
                message="training queued",
                sample_filename="first.wav",
                sample_filenames=["first.wav"],
                sample_count=1,
                job_id="job-123",
            ),
        )

        response = client.get(f"/api/v1/clones/{profile.clone_id}/voice/status")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        persisted = store.load_voice_status(profile.clone_id)

        self.assertEqual(body["voice"]["status"], "ready")
        self.assertEqual(body["voice"]["model_id"], "voice-model-123")
        self.assertEqual(body["voice"]["job_id"], "job-123")
        self.assertIsNotNone(persisted)
        self.assertEqual(persisted.status, "ready")
        self.assertEqual(persisted.model_id, "voice-model-123")

    def test_chat_correction_message_is_persisted_and_acknowledged(self):
        client = self._build_client()
        user = self._register(client)
        store = CloneStore(paths.DATA_ROOT, user_id=user["id"])
        profile = store.create_clone(
            target_name="Target",
            chat_text="Target: 哈哈哈我来了",
        )

        response = client.post(
            f"/api/v1/clones/{profile.clone_id}/chat",
            json={"message": "ta不会这样说，不要再说哈哈哈"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        persisted_profile = store.load_clone(profile.clone_id)
        self.assertIn("记住", body["reply"]["text"])
        self.assertEqual(persisted_profile.corrections, ["不要再说哈哈哈"])


if __name__ == "__main__":
    unittest.main()
