import unittest

import scripts.mock_api_smoke as smoke_module
from scripts.mock_api_smoke import SmokeError, run_smoke


class MockApiSmokeTests(unittest.TestCase):
    def test_run_smoke_exercises_mock_voice_chat_flow(self):
        client = FakeSmokeClient(
            {
                ("GET", "/api/health"): {"ok": True},
                ("POST", "/api/clones"): {"clone": {"cloneId": "clone-1"}},
                ("POST", "/api/clones/clone-1/voice/samples"): {
                    "voice": {"status": "samples_ready", "sample_count": 2}
                },
                ("POST", "/api/clones/clone-1/voice/train"): {
                    "voice": {"status": "ready", "adapter": "mock"}
                },
                ("GET", "/api/clones/clone-1/voice/status"): {
                    "voice": {"status": "ready", "adapter": "mock", "sample_count": 2}
                },
                ("POST", "/api/clones/clone-1/chat"): {
                    "reply": {"text": "hey there", "emotion": "warm"}
                },
                ("POST", "/api/clones/clone-1/speak"): {
                    "speech": {
                        "backend": "mock",
                        "audioDataUrl": "data:audio/wav;base64,UklGRg==",
                    }
                },
            }
        )

        summary = run_smoke(client)

        self.assertEqual(
            client.calls,
            [
                ("GET", "/api/health", None),
                (
                    "POST",
                    "/api/clones",
                    {
                        "targetName": "Smoke Target",
                        "chatText": "Smoke Target: hello\nUser: say something short",
                        "voiceFiles": [
                            {"name": "smoke-sample.wav", "data": "data:audio/wav;base64,UklGRg=="}
                        ],
                    },
                ),
                (
                    "POST",
                    "/api/clones/clone-1/voice/samples",
                    {
                        "voiceFiles": [
                            {"name": "smoke-extra.wav", "data": "data:audio/wav;base64,UklGRg=="}
                        ],
                    },
                ),
                ("POST", "/api/clones/clone-1/voice/train", {}),
                ("GET", "/api/clones/clone-1/voice/status", None),
                ("POST", "/api/clones/clone-1/chat", {"message": "say something in your usual style"}),
                ("POST", "/api/clones/clone-1/speak", {"text": "hey there", "emotion": "warm"}),
            ],
        )
        self.assertEqual(
            summary,
            {
                "cloneId": "clone-1",
                "voiceStatus": "ready",
                "voiceSampleCount": 2,
                "replyText": "hey there",
                "speechBackend": "mock",
            },
        )

    def test_run_smoke_rejects_missing_audio_data_url(self):
        client = FakeSmokeClient(
            {
                ("GET", "/api/health"): {"ok": True},
                ("POST", "/api/clones"): {"clone": {"cloneId": "clone-1"}},
                ("POST", "/api/clones/clone-1/voice/samples"): {
                    "voice": {"status": "samples_ready", "sample_count": 2}
                },
                ("POST", "/api/clones/clone-1/voice/train"): {
                    "voice": {"status": "ready", "adapter": "mock"}
                },
                ("GET", "/api/clones/clone-1/voice/status"): {"voice": {"status": "ready"}},
                ("POST", "/api/clones/clone-1/chat"): {"reply": {"text": "hey there"}},
                ("POST", "/api/clones/clone-1/speak"): {"speech": {"backend": "mock"}},
            }
        )

        with self.assertRaisesRegex(SmokeError, "audioDataUrl"):
            run_smoke(client)

    def test_smoke_client_bypasses_proxy_settings_for_local_api(self):
        build_calls = []

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc, tb):
                return False

            def read(self):
                return b'{"ok": true}'

        class FakeOpener:
            def open(self, req, timeout):
                build_calls.append(("open", req.full_url, timeout))
                return FakeResponse()

        def fake_build_opener(*handlers):
            build_calls.append(("handlers", handlers))
            self.assertEqual(len(handlers), 1)
            self.assertIsInstance(handlers[0], smoke_module.request.ProxyHandler)
            self.assertEqual(handlers[0].proxies, {})
            return FakeOpener()

        original_build_opener = smoke_module.request.build_opener
        try:
            smoke_module.request.build_opener = fake_build_opener

            result = smoke_module.SmokeClient("http://127.0.0.1:8792").get_json("/api/health")
        finally:
            smoke_module.request.build_opener = original_build_opener

        self.assertEqual(result, {"ok": True})
        self.assertEqual(build_calls[0][0], "handlers")


class FakeSmokeClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def get_json(self, path):
        self.calls.append(("GET", path, None))
        return self.responses[(self.calls[-1][0], path)]

    def post_json(self, path, payload):
        self.calls.append(("POST", path, payload))
        return self.responses[(self.calls[-1][0], path)]
