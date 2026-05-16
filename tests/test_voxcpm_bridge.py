import base64
from tempfile import TemporaryDirectory
import unittest
from pathlib import Path

from cyberclone.voxcpm_bridge import (
    SynthesisRequest,
    create_synthesis_response,
    create_training_response,
    decode_synthesis_payload,
)


class VoxCPMBridgeTests(unittest.TestCase):
    def test_training_response_marks_reference_voice_ready(self):
        response = create_training_response(
            {
                "cloneId": "abc123",
                "voiceName": "Target",
                "samplePaths": ["D:/samples/a.wav", "D:/samples/b.wav"],
                "sampleFilenames": ["a.wav", "b.wav"],
            }
        )

        self.assertEqual(response["status"], "ready")
        self.assertEqual(response["adapter"], "voxcpm-reference")
        self.assertEqual(response["modelId"], "voxcpm-reference-abc123")
        self.assertEqual(response["sampleCount"], 2)
        self.assertIn("reference", response["message"])

    def test_training_response_rejects_missing_samples(self):
        with self.assertRaises(ValueError):
            create_training_response({"cloneId": "abc123", "samplePaths": []})

    def test_training_response_prefers_embedded_sample_files_over_unshared_paths(self):
        audio_data = f"data:audio/wav;base64,{base64.b64encode(b'RIFFsample').decode('ascii')}"

        with TemporaryDirectory() as temp_dir:
            response = create_training_response(
                {
                    "cloneId": "abc123",
                    "voiceName": "Target",
                    "samplePaths": ["Z:/unshared/first.wav"],
                    "sampleFiles": [
                        {
                            "name": "first.wav",
                            "contentType": "audio/wav",
                            "data": audio_data,
                        }
                    ],
                },
                storage_root=Path(temp_dir),
            )

            saved_path = Path(response["samplePaths"][0])
            self.assertEqual(response["status"], "ready")
            self.assertEqual(response["sampleCount"], 1)
            self.assertEqual(response["sampleFilenames"], ["first.wav"])
            self.assertNotEqual(saved_path, Path("Z:/unshared/first.wav"))
            self.assertEqual(saved_path.read_bytes(), b"RIFFsample")

    def test_decode_synthesis_payload_maps_emotion_to_control_prompt(self):
        request = decode_synthesis_payload(
            {
                "text": "你好",
                "emotion": "warm",
                "cloneId": "abc123",
                "voiceName": "Target",
                "referenceAudioPath": "D:/samples/a.wav",
            }
        )

        self.assertEqual(request.text, "你好")
        self.assertEqual(request.emotion, "warm")
        self.assertEqual(request.clone_id, "abc123")
        self.assertEqual(request.voice_name, "Target")
        self.assertEqual(request.reference_audio_path, Path("D:/samples/a.wav"))
        self.assertIn("温柔", request.control_prompt)

    def test_decode_synthesis_payload_rejects_missing_text(self):
        with self.assertRaises(ValueError):
            decode_synthesis_payload({"emotion": "warm"})

    def test_decode_synthesis_payload_uses_embedded_reference_audio_file(self):
        audio_data = f"data:audio/wav;base64,{base64.b64encode(b'RIFFreference').decode('ascii')}"

        with TemporaryDirectory() as temp_dir:
            request = decode_synthesis_payload(
                {
                    "text": "hello",
                    "emotion": "warm",
                    "referenceAudioPath": "Z:/unshared/reference.wav",
                    "referenceAudioFile": {
                        "name": "reference.wav",
                        "contentType": "audio/wav",
                        "data": audio_data,
                    },
                },
                storage_root=Path(temp_dir),
            )

            self.assertNotEqual(request.reference_audio_path, Path("Z:/unshared/reference.wav"))
            self.assertEqual(request.reference_audio_path.name, "reference.wav")
            self.assertEqual(request.reference_audio_path.read_bytes(), b"RIFFreference")

    def test_synthesis_response_encodes_wav_from_engine(self):
        engine = FakeEngine(b"RIFFfake-wav")
        response = create_synthesis_response(
            engine,
            {
                "text": "你好",
                "emotion": "happy",
                "cloneId": "abc123",
                "voiceName": "Target",
                "referenceAudioPath": "D:/samples/a.wav",
            },
        )

        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["contentType"], "audio/wav")
        self.assertEqual(base64.b64decode(response["audioBase64"]), b"RIFFfake-wav")
        self.assertEqual(engine.last_request.emotion, "happy")
        self.assertIn("明亮", engine.last_request.control_prompt)


class FakeEngine:
    def __init__(self, wav_bytes: bytes) -> None:
        self.wav_bytes = wav_bytes
        self.last_request: SynthesisRequest | None = None

    def synthesize(self, request: SynthesisRequest) -> bytes:
        self.last_request = request
        return self.wav_bytes


if __name__ == "__main__":
    unittest.main()
