import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class DocumentationTests(unittest.TestCase):
    def test_readme_has_readable_voice_setup_and_verification_steps(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")

        for expected in (
            "语音样本",
            "训练音色",
            "双模式聊天",
            "Mock 端到端验证",
            "用 mock 后端跑完整流程",
            "VOICE_TTS_BACKEND=mock",
            "VOICE_TRAINING_BACKEND=mock",
            "VOICE_TTS_INCLUDE_REFERENCE_AUDIO",
            "VOICE_TRAINING_INCLUDE_AUDIO",
            "python -m cyberclone.web --port 8787",
            "rules.md",
        ):
            self.assertIn(expected, readme)

        for mojibake in ("è¯­", "è®­", "éŸ³", "é‘±", "ç’‡", "é™", "é—Š", "éŽ¯", "å¯®â‚¬", "é–º", "é", "ç€µ"):
            self.assertNotIn(mojibake, readme)
