import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class LocalImportUiTests(unittest.TestCase):
    def test_upload_flow_is_local_file_only(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        web_api = (ROOT / "src" / "cyberclone" / "web.py").read_text(encoding="utf-8")

        self.assertNotIn("WeFlow", html)
        self.assertNotIn("weflow", html.lower())
        self.assertNotIn("weflow", script.lower())
        self.assertNotIn("/api/weflow", web_api)
        self.assertNotIn("WeFlow", web_api)
        self.assertNotIn("data-text-source", html)

        for element_id in ("chat-file", "voice-file"):
            self.assertIn(f'id="{element_id}"', html)

        for removed_element_id in (
            "image-files",
            "video-files",
            "sticker-files",
            "moments-files",
        ):
            self.assertNotIn(f'id="{removed_element_id}"', html)

        self.assertIn('id="chat-file" name="chatFile" type="file" accept=".txt,.json,.csv,.md" multiple', html)
        self.assertIn('id="voice-file" name="voiceFile" type="file" accept="audio/*,.wav,.mp3,.m4a,.ogg" multiple', html)
        self.assertIn("voiceFiles", script)
