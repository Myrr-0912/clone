import json
import tempfile
import unittest
from pathlib import Path

from cyberclone.voice_models import (
    create_or_update_voice_manifest,
    load_voice_manifest,
    voice_artifact_size,
    voice_resource_summary,
)


class VoiceModelManifestTests(unittest.TestCase):
    def test_manifest_writes_required_fields_and_binds_vector_db_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "user-a" / "clone-a" / "voice" / "manifest.json"
            vector_db_path = root / "user-a" / "clone-a" / "vector" / "chat_index.json"
            artifact_path = root / "user-a" / "clone-a" / "voice" / "model.bin"

            manifest = create_or_update_voice_manifest(
                manifest_path,
                user_id="user-a",
                clone_id="clone-a",
                clone_name="Dad",
                vector_db_path=vector_db_path,
                status="queued",
                backend="mock",
                model_id="model-a",
                job_id="job-a",
                sample_filenames=["samples/first.wav", "../second.mp3"],
                artifact_path=artifact_path,
                updated_at="2026-05-17T00:00:00Z",
            )

            self.assertTrue(manifest_path.exists())
            self.assertEqual(manifest["userId"], "user-a")
            self.assertEqual(manifest["cloneId"], "clone-a")
            self.assertEqual(manifest["cloneName"], "Dad")
            self.assertEqual(manifest["vectorDbPath"], str(vector_db_path))
            self.assertEqual(manifest["status"], "queued")
            self.assertEqual(manifest["backend"], "mock")
            self.assertEqual(manifest["modelId"], "model-a")
            self.assertEqual(manifest["jobId"], "job-a")
            self.assertEqual(manifest["sampleCount"], 2)
            self.assertEqual(manifest["sampleFilenames"], ["first.wav", "second.mp3"])
            self.assertEqual(manifest["artifactPath"], str(artifact_path))
            self.assertEqual(manifest["updatedAt"], "2026-05-17T00:00:00Z")
            self.assertEqual(load_voice_manifest(manifest_path), manifest)

            raw = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(
                set(raw),
                {
                    "userId",
                    "cloneId",
                    "cloneName",
                    "vectorDbPath",
                    "status",
                    "backend",
                    "modelId",
                    "jobId",
                    "sampleCount",
                    "sampleFilenames",
                    "artifactPath",
                    "updatedAt",
                },
            )

    def test_same_clone_name_is_isolated_by_user_and_clone_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = create_or_update_voice_manifest(
                root / "user-a" / "clone-a" / "voice" / "manifest.json",
                user_id="user-a",
                clone_id="clone-a",
                clone_name="\u7238\u7238",
                vector_db_path=root / "user-a" / "clone-a" / "vector" / "chat_index.json",
                sample_filenames=["dad.wav"],
                updated_at="2026-05-17T00:00:00Z",
            )
            second = create_or_update_voice_manifest(
                root / "user-b" / "clone-b" / "voice" / "manifest.json",
                user_id="user-b",
                clone_id="clone-b",
                clone_name="\u7238\u7238",
                vector_db_path=root / "user-b" / "clone-b" / "vector" / "chat_index.json",
                sample_filenames=["dad.wav"],
                updated_at="2026-05-17T00:00:00Z",
            )

            self.assertEqual(first["cloneName"], second["cloneName"])
            self.assertNotEqual(first["userId"], second["userId"])
            self.assertNotEqual(first["cloneId"], second["cloneId"])
            self.assertNotEqual(first["vectorDbPath"], second["vectorDbPath"])

    def test_manifest_update_refreshes_sample_count_and_model_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "user-a" / "clone-a" / "voice" / "manifest.json"
            vector_db_path = root / "user-a" / "clone-a" / "vector" / "chat_index.json"

            create_or_update_voice_manifest(
                manifest_path,
                user_id="user-a",
                clone_id="clone-a",
                clone_name="Dad",
                vector_db_path=vector_db_path,
                status="queued",
                backend="http",
                job_id="job-1",
                sample_filenames=["first.wav"],
                updated_at="2026-05-17T00:00:00Z",
            )

            updated = create_or_update_voice_manifest(
                manifest_path,
                user_id="user-a",
                clone_id="clone-a",
                clone_name="Dad",
                vector_db_path=vector_db_path,
                status="ready",
                backend="http",
                model_id="voice-model-1",
                job_id="job-2",
                sample_filenames=["first.wav", "second.wav"],
                updated_at="2026-05-17T00:01:00Z",
            )

            self.assertEqual(updated["status"], "ready")
            self.assertEqual(updated["modelId"], "voice-model-1")
            self.assertEqual(updated["jobId"], "job-2")
            self.assertEqual(updated["sampleCount"], 2)
            self.assertEqual(updated["sampleFilenames"], ["first.wav", "second.wav"])
            self.assertEqual(updated["vectorDbPath"], str(vector_db_path))
            self.assertEqual(load_voice_manifest(manifest_path), updated)

    def test_artifact_size_and_resource_summary_report_model_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_path = root / "user-a" / "clone-a" / "voice" / "manifest.json"
            artifact_path = root / "user-a" / "clone-a" / "voice" / "model.bin"
            artifact_path.parent.mkdir(parents=True)
            artifact_path.write_bytes(b"voice-model")

            create_or_update_voice_manifest(
                manifest_path,
                user_id="user-a",
                clone_id="clone-a",
                clone_name="Dad",
                vector_db_path=root / "user-a" / "clone-a" / "vector" / "chat_index.json",
                status="ready",
                backend="local",
                model_id="voice-model-1",
                sample_filenames=["first.wav", "second.wav"],
                artifact_path=artifact_path,
                updated_at="2026-05-17T00:00:00Z",
            )

            self.assertEqual(voice_artifact_size(artifact_path), len(b"voice-model"))
            self.assertEqual(voice_artifact_size(root / "missing.bin"), 0)

            summary = voice_resource_summary(manifest_path)

            self.assertEqual(summary["manifestPath"], str(manifest_path))
            self.assertEqual(summary["artifactSize"], len(b"voice-model"))
            self.assertEqual(summary["sampleCount"], 2)
            self.assertEqual(summary["status"], "ready")


if __name__ == "__main__":
    unittest.main()
