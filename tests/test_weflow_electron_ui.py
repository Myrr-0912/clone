import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WEFLOW_ROOT = ROOT / "weflow-src"


class WeFlowElectronUiTests(unittest.TestCase):
    def test_cyber_clone_page_can_load_existing_clone_by_id(self):
        page = (WEFLOW_ROOT / "src" / "pages" / "CyberClonePage.tsx").read_text(encoding="utf-8")

        self.assertIn("type BusyAction = 'create' | 'load' | 'samples' | 'train' | 'status' | 'send' | null", page)
        self.assertIn("const handleLoadClone = async () =>", page)
        self.assertIn("voiceChat.getClone(normalizedCloneId)", page)
        self.assertIn("setTargetName(clone.name || targetName)", page)
        self.assertIn("setSampleNames(combineSampleNames([], [], nextVoice))", page)
        self.assertIn("setConversation([])", page)
        self.assertIn("onClick={handleLoadClone}", page)

    def test_cyber_clone_training_status_marks_queued_and_running_as_training(self):
        page = (WEFLOW_ROOT / "src" / "pages" / "CyberClonePage.tsx").read_text(encoding="utf-8")

        self.assertIn("['queued', 'running'].includes(status.status)", page)

    def test_cyber_clone_page_has_readable_chinese_labels(self):
        page = (WEFLOW_ROOT / "src" / "pages" / "CyberClonePage.tsx").read_text(encoding="utf-8")

        for expected in (
            "语音模型与双模式聊天",
            "模型资料",
            "聊天样本",
            "选择语音样本",
            "录制样本",
            "停止录制",
            "训练状态",
            "追加样本",
            "保存样本",
            "训练音色",
            "对话",
            "文本",
            "语音",
            "发送并合成",
        ):
            self.assertIn(expected, page)

        for mojibake in ("璇", "鍒", "寰", "褰", "鎯", "闊", "鐘", "鏍", "妗", "鑱"):
            self.assertNotIn(mojibake, page)
