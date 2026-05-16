import json
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib import request

import cyberclone.web as web_module
from cyberclone.models import VoiceTrainingStatus
from cyberclone.storage import CloneStore
from cyberclone.web import (
    CloneRequestHandler,
    decode_speech_payload,
    decode_upload_payload,
    decode_voice_samples_payload,
)


class WebApiTests(unittest.TestCase):
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
        payload = {
            "targetName": "Target",
            "chatText": "Target: hi",
        }
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

    def test_get_voice_status_returns_persisted_training_status(self):
        original_data_root = web_module.DATA_ROOT
        original_refresh = web_module.refresh_voice_training_status
        body = None
        with tempfile.TemporaryDirectory() as tmp:
            web_module.DATA_ROOT = Path(tmp)
            try:
                web_module.refresh_voice_training_status = lambda profile, current, env_path=None: current
                store = CloneStore(web_module.DATA_ROOT)
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

                server = ThreadingHTTPServer(("127.0.0.1", 0), CloneRequestHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    opener = request.build_opener(request.ProxyHandler({}))
                    with opener.open(
                        f"http://127.0.0.1:{server.server_port}/api/clones/{profile.clone_id}/voice/status",
                        timeout=5,
                    ) as response:
                        body = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
            finally:
                web_module.DATA_ROOT = original_data_root
                web_module.refresh_voice_training_status = original_refresh

        self.assertEqual(body["voice"]["status"], "queued")
        self.assertEqual(body["voice"]["job_id"], "job-123")
        self.assertEqual(body["clone"]["cloneId"], profile.clone_id)

    def test_get_voice_status_refreshes_and_persists_external_training_status(self):
        original_data_root = web_module.DATA_ROOT
        original_refresh = web_module.refresh_voice_training_status
        body = None
        persisted_status = None
        with tempfile.TemporaryDirectory() as tmp:
            web_module.DATA_ROOT = Path(tmp)
            try:
                store = CloneStore(web_module.DATA_ROOT)
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

                web_module.refresh_voice_training_status = fake_refresh
                server = ThreadingHTTPServer(("127.0.0.1", 0), CloneRequestHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    opener = request.build_opener(request.ProxyHandler({}))
                    with opener.open(
                        f"http://127.0.0.1:{server.server_port}/api/clones/{profile.clone_id}/voice/status",
                        timeout=5,
                    ) as response:
                        body = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                persisted_status = store.load_voice_status(profile.clone_id)
            finally:
                web_module.DATA_ROOT = original_data_root
                web_module.refresh_voice_training_status = original_refresh

        self.assertEqual(body["voice"]["status"], "ready")
        self.assertEqual(body["voice"]["model_id"], "voice-model-123")
        self.assertEqual(body["voice"]["job_id"], "job-123")
        self.assertIsNotNone(persisted_status)
        self.assertEqual(persisted_status.status, "ready")
        self.assertEqual(persisted_status.model_id, "voice-model-123")

    def test_chat_correction_message_is_persisted_and_acknowledged(self):
        original_data_root = web_module.DATA_ROOT
        body = None
        persisted_profile = None
        with tempfile.TemporaryDirectory() as tmp:
            web_module.DATA_ROOT = Path(tmp)
            try:
                store = CloneStore(web_module.DATA_ROOT)
                profile = store.create_clone(
                    target_name="Target",
                    chat_text="Target: 哈哈哈 我来了",
                )

                server = ThreadingHTTPServer(("127.0.0.1", 0), CloneRequestHandler)
                thread = threading.Thread(target=server.serve_forever, daemon=True)
                thread.start()
                try:
                    opener = request.build_opener(request.ProxyHandler({}))
                    req = request.Request(
                        f"http://127.0.0.1:{server.server_port}/api/clones/{profile.clone_id}/chat",
                        data=json.dumps({"message": "ta不会这样说，不要再说哈哈哈"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    )
                    with opener.open(req, timeout=5) as response:
                        body = json.loads(response.read().decode("utf-8"))
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join(timeout=5)
                persisted_profile = store.load_clone(profile.clone_id)
            finally:
                web_module.DATA_ROOT = original_data_root

        self.assertIn("记住", body["reply"]["text"])
        self.assertEqual(persisted_profile.corrections, ["不要再说哈哈哈"])
