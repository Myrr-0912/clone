import unittest
import base64
import io
from pathlib import Path
import tempfile
from urllib import error

import cyberclone.voice as voice_module
from cyberclone.models import CloneMemory, CloneProfile, CloneStyle, VoiceTrainingStatus
from cyberclone.voice import (
    create_voice_training_status,
    refresh_voice_training_status,
    synthesize_speech,
    train_voice_model,
)


class VoiceTests(unittest.TestCase):
    def test_training_status_lists_all_voice_samples(self):
        status = create_voice_training_status(["first.wav", "../second.mp3"])

        self.assertEqual(status.status, "samples_ready")
        self.assertEqual(status.sample_count, 2)
        self.assertEqual(status.sample_filename, "first.wav")
        self.assertEqual(status.sample_filenames, ["first.wav", "second.mp3"])
        self.assertIsNone(status.error)

    def test_synthesis_degrades_without_configured_backend(self):
        result = synthesize_speech(
            profile=_profile(),
            text="你好",
            reference_audio_path=None,
            emotion="warm",
            env={},
        )

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.backend, "none")
        self.assertIsNone(result.audio_data_url)
        self.assertIn("VOICE_TTS_BACKEND", result.message)

    def test_mock_synthesis_returns_playable_wav_data_url(self):
        result = synthesize_speech(
            profile=_profile(),
            text="你好",
            reference_audio_path=None,
            emotion="warm",
            env={"VOICE_TTS_BACKEND": "mock"},
        )

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.backend, "mock")
        self.assertEqual(result.content_type, "audio/wav")
        self.assertTrue(result.audio_data_url.startswith("data:audio/wav;base64,"))
        self.assertEqual(result.emotion, "warm")

    def test_http_synthesis_sends_trained_voice_metadata(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"audioBase64": "UklGRg==", "contentType": "audio/wav"}

        profile = _profile()
        profile.voice = VoiceTrainingStatus(
            status="ready",
            adapter="http",
            message="voice ready",
            sample_filename="first.wav",
            sample_filenames=["first.wav", "second.wav"],
            sample_count=2,
            model_id="voice-model-1",
            job_id="job-1",
        )
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            result = synthesize_speech(
                profile=profile,
                text="hello",
                reference_audio_path=Path("D:/samples/first.wav"),
                emotion="warm",
                env={
                    "VOICE_TTS_BACKEND": "http",
                    "VOICE_TTS_URL": "http://127.0.0.1:9000/speak",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "ok")
        url, headers, payload, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:9000/speak")
        self.assertEqual(payload["modelId"], "voice-model-1")
        self.assertEqual(payload["jobId"], "job-1")
        self.assertEqual(payload["sampleFilenames"], ["first.wav", "second.wav"])
        self.assertEqual(payload["voiceStatus"], "ready")
        self.assertGreater(timeout, 0)

    def test_http_synthesis_sends_configured_emotion_controls(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"audioBase64": "UklGRg==", "contentType": "audio/wav"}

        profile = _profile()
        profile.voice = VoiceTrainingStatus(
            status="ready",
            adapter="http",
            message="voice ready",
            sample_filename="first.wav",
            sample_filenames=["first.wav"],
            sample_count=1,
            model_id="voice-model-1",
        )
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            result = synthesize_speech(
                profile=profile,
                text="hello",
                reference_audio_path=Path("D:/samples/first.wav"),
                emotion="warm",
                env={
                    "VOICE_TTS_BACKEND": "http",
                    "VOICE_TTS_URL": "http://127.0.0.1:9000/speak",
                    "VOICE_TTS_CONTROL_PROMPT_WARM": "gentle, close, patient voice",
                    "VOICE_TTS_CFG_VALUE": "2.6",
                    "VOICE_TTS_INFERENCE_STEPS": "8",
                    "VOICE_TTS_NORMALIZE": "true",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "ok")
        payload = calls[0][2]
        self.assertEqual(payload["controlPrompt"], "gentle, close, patient voice")
        self.assertEqual(payload["cfgValue"], 2.6)
        self.assertEqual(payload["inferenceSteps"], 8)
        self.assertIs(payload["normalize"], True)

    def test_http_synthesis_surfaces_backend_error_payload(self):
        def fake_post_json(url, headers, payload, timeout):
            return {
                "status": "error",
                "message": "Voice model is still training.",
                "error": "model_not_ready",
            }

        profile = _profile()
        profile.voice = VoiceTrainingStatus(
            status="running",
            adapter="http",
            message="voice training",
            sample_filename="first.wav",
            sample_filenames=["first.wav"],
            sample_count=1,
            job_id="job-1",
        )
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            result = synthesize_speech(
                profile=profile,
                text="hello",
                reference_audio_path=Path("D:/samples/first.wav"),
                emotion="warm",
                env={
                    "VOICE_TTS_BACKEND": "http",
                    "VOICE_TTS_URL": "http://127.0.0.1:9000/speak",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "error")
        self.assertEqual(result.backend, "http")
        self.assertEqual(result.message, "Voice model is still training. (model_not_ready)")
        self.assertIsNone(result.audio_data_url)

    def test_http_synthesis_can_embed_reference_audio_when_configured(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {"audioBase64": "UklGRg==", "contentType": "audio/wav"}

        profile = _profile()
        profile.voice = VoiceTrainingStatus(
            status="ready",
            adapter="http",
            message="voice ready",
            sample_filename="first.wav",
            sample_filenames=["first.wav"],
            sample_count=1,
            model_id="voice-model-1",
        )
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            with tempfile.TemporaryDirectory() as tmp:
                sample_path = Path(tmp) / "first.wav"
                sample_path.write_bytes(b"RIFFvoice")
                result = synthesize_speech(
                    profile=profile,
                    text="hello",
                    reference_audio_path=sample_path,
                    emotion="warm",
                    env={
                        "VOICE_TTS_BACKEND": "http",
                        "VOICE_TTS_URL": "http://127.0.0.1:9000/speak",
                        "VOICE_TTS_INCLUDE_REFERENCE_AUDIO": "true",
                    },
                )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "ok")
        payload = calls[0][2]
        self.assertEqual(payload["referenceAudioFile"]["name"], "first.wav")
        self.assertEqual(payload["referenceAudioFile"]["contentType"], "audio/wav")
        self.assertEqual(
            payload["referenceAudioFile"]["data"],
            f"data:audio/wav;base64,{base64.b64encode(b'RIFFvoice').decode('ascii')}",
        )

    def test_http_synthesis_requires_reference_sample_or_trained_model(self):
        def fail_post_json(*args, **kwargs):
            raise AssertionError("HTTP TTS should not be called without voice identity metadata")

        original_post_json = voice_module._post_json
        voice_module._post_json = fail_post_json
        try:
            result = synthesize_speech(
                profile=_profile(),
                text="hello",
                reference_audio_path=None,
                emotion="warm",
                env={
                    "VOICE_TTS_BACKEND": "http",
                    "VOICE_TTS_URL": "http://127.0.0.1:9000/speak",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "unavailable")
        self.assertEqual(result.backend, "http")
        self.assertIsNone(result.audio_data_url)
        self.assertIn("voice sample", result.message)

    def test_training_requires_voice_samples(self):
        result = train_voice_model(
            profile=_profile(),
            sample_paths=[],
            env={"VOICE_TRAINING_BACKEND": "mock"},
        )

        self.assertEqual(result.status, "missing_samples")
        self.assertEqual(result.error, "missing_samples")
        self.assertIn("Upload voice samples", result.message)

    def test_mock_training_marks_voice_model_ready(self):
        profile = _profile()
        profile.voice = create_voice_training_status(["first.wav", "second.wav"])

        result = train_voice_model(
            profile=profile,
            sample_paths=[Path("first.wav"), Path("second.wav")],
            env={"VOICE_TRAINING_BACKEND": "mock"},
        )

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.adapter, "mock")
        self.assertEqual(result.sample_count, 2)
        self.assertEqual(result.sample_filenames, ["first.wav", "second.wav"])
        self.assertTrue(result.model_id.startswith("mock-"))

    def test_http_training_posts_samples_and_reads_job_ids(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "status": "queued",
                "message": "training queued",
                "modelId": "voice-model-1",
                "jobId": "job-1",
            }

        profile = _profile()
        profile.voice = create_voice_training_status(["first.wav"])
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            result = train_voice_model(
                profile=profile,
                sample_paths=[Path("D:/samples/first.wav")],
                env={
                    "VOICE_TRAINING_BACKEND": "http",
                    "VOICE_TRAINING_URL": "http://127.0.0.1:9000/train",
                    "VOICE_TRAINING_API_KEY": "secret",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "queued")
        self.assertEqual(result.model_id, "voice-model-1")
        self.assertEqual(result.job_id, "job-1")
        url, headers, payload, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:9000/train")
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertEqual(payload["cloneId"], "abc")
        self.assertEqual(payload["sampleFilenames"], ["first.wav"])
        self.assertEqual(payload["samplePaths"], ["D:\\samples\\first.wav"])
        self.assertGreater(timeout, 0)

    def test_http_training_can_embed_sample_audio_when_configured(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "status": "queued",
                "message": "training queued",
                "jobId": "job-1",
            }

        profile = _profile()
        profile.voice = create_voice_training_status(["first.wav"])
        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            with tempfile.TemporaryDirectory() as tmp:
                sample_path = Path(tmp) / "first.wav"
                sample_path.write_bytes(b"RIFFaudio")
                result = train_voice_model(
                    profile=profile,
                    sample_paths=[sample_path],
                    env={
                        "VOICE_TRAINING_BACKEND": "http",
                        "VOICE_TRAINING_URL": "http://127.0.0.1:9000/train",
                        "VOICE_TRAINING_INCLUDE_AUDIO": "true",
                    },
                )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "queued")
        payload = calls[0][2]
        self.assertEqual(payload["sampleFiles"][0]["name"], "first.wav")
        self.assertEqual(payload["sampleFiles"][0]["contentType"], "audio/wav")
        self.assertEqual(
            payload["sampleFiles"][0]["data"],
            f"data:audio/wav;base64,{base64.b64encode(b'RIFFaudio').decode('ascii')}",
        )

    def test_http_training_status_refresh_preserves_samples(self):
        calls = []

        def fake_post_json(url, headers, payload, timeout):
            calls.append((url, headers, payload, timeout))
            return {
                "status": "ready",
                "message": "voice model ready",
                "modelId": "voice-model-1",
                "jobId": "job-1",
            }

        profile = _profile()
        current = create_voice_training_status(["first.wav", "second.wav"])
        current.status = "queued"
        current.adapter = "http"
        current.message = "training queued"
        current.job_id = "job-1"
        profile.voice = current

        original_post_json = voice_module._post_json
        voice_module._post_json = fake_post_json
        try:
            result = refresh_voice_training_status(
                profile=profile,
                current=current,
                env={
                    "VOICE_TRAINING_BACKEND": "http",
                    "VOICE_TRAINING_STATUS_URL": "http://127.0.0.1:9000/status",
                    "VOICE_TRAINING_API_KEY": "secret",
                },
            )
        finally:
            voice_module._post_json = original_post_json

        self.assertEqual(result.status, "ready")
        self.assertEqual(result.message, "voice model ready")
        self.assertEqual(result.model_id, "voice-model-1")
        self.assertEqual(result.job_id, "job-1")
        self.assertEqual(result.sample_filename, "first.wav")
        self.assertEqual(result.sample_filenames, ["first.wav", "second.wav"])
        self.assertEqual(result.sample_count, 2)
        url, headers, payload, timeout = calls[0]
        self.assertEqual(url, "http://127.0.0.1:9000/status")
        self.assertEqual(headers["Authorization"], "Bearer secret")
        self.assertEqual(payload["cloneId"], "abc")
        self.assertEqual(payload["jobId"], "job-1")
        self.assertEqual(payload["modelId"], "")
        self.assertGreater(timeout, 0)

    def test_post_json_bypasses_proxy_for_loopback_urls(self):
        calls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true}'

        class FakeOpener:
            def open(self, req, timeout):
                calls.append(("opener.open", req.full_url, timeout))
                return FakeResponse()

        def fake_build_opener(proxy_handler):
            calls.append(("build_opener", proxy_handler.__class__.__name__))
            return FakeOpener()

        def fail_urlopen(*args, **kwargs):
            raise AssertionError("loopback voice API calls must not use global proxy-aware urlopen")

        original_build_opener = voice_module.request.build_opener
        original_urlopen = voice_module.request.urlopen
        voice_module.request.build_opener = fake_build_opener
        voice_module.request.urlopen = fail_urlopen
        try:
            response = voice_module._post_json(
                "http://127.0.0.1:8810/speak",
                {"Content-Type": "application/json"},
                {"text": "hello"},
                3.0,
            )
        finally:
            voice_module.request.build_opener = original_build_opener
            voice_module.request.urlopen = original_urlopen

        self.assertEqual(response, {"ok": True})
        self.assertEqual(calls[0][0], "build_opener")
        self.assertEqual(calls[1], ("opener.open", "http://127.0.0.1:8810/speak", 3.0))

    def test_post_json_formats_json_http_error_payloads(self):
        def fail_urlopen(*args, **kwargs):
            raise error.HTTPError(
                url="https://voice.example.test/speak",
                code=503,
                msg="Service Unavailable",
                hdrs={},
                fp=io.BytesIO(b'{"message":"Voice backend warming up","error":"model_loading"}'),
            )

        original_urlopen = voice_module.request.urlopen
        voice_module.request.urlopen = fail_urlopen
        try:
            with self.assertRaisesRegex(
                RuntimeError,
                r"HTTP 503: Voice backend warming up \(model_loading\)",
            ):
                voice_module._post_json(
                    "https://voice.example.test/speak",
                    {"Content-Type": "application/json"},
                    {"text": "hello"},
                    3.0,
                )
        finally:
            voice_module.request.urlopen = original_urlopen


def _profile() -> CloneProfile:
    return CloneProfile(
        clone_id="abc",
        name="Target",
        style=CloneStyle(catchphrases=["哈哈哈"], punctuation=["。"], average_length=6),
        memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身"),
        source_stats={"target_messages": 2},
    )
