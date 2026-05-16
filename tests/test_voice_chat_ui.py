import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class VoiceChatUiTests(unittest.TestCase):
    def test_dual_mode_chat_controls_are_present(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        for element_id in (
            "clone-id-input",
            "load-clone-button",
            "sample-list",
            "training-state",
            "chat-mode-text",
            "chat-mode-voice",
            "voice-emotion",
            "audio-playback",
            "voice-upload-button",
            "voice-train-button",
            "voice-refresh-button",
        ):
            self.assertIn(f'id="{element_id}"', html)

    def test_key_voice_chat_labels_are_readable_chinese(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        for label in (
            "聊天文本文件",
            "语音文件",
            "语音样本",
            "保存样本",
            "训练音色",
            "刷新状态",
            "文本",
            "语音",
            "情绪",
            "开心",
        ):
            self.assertIn(label, html)

        self.assertIn('<option value="happy">开心</option>', html)
        for mojibake in ("è¯­", "è®­", "éŸ³", "é‘±", "ç’‡", "é’é”‹æŸŠ", "éŽ¯å‘¯åŽ", "å¯®â‚¬è¹‡"):
            self.assertNotIn(mojibake, html)
        self.assertNotIn("&#", html)

    def test_voice_chat_markup_does_not_leave_orphan_closing_tag_text(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")

        html_without_valid_button_closers = html.replace("</button>", "")
        html_without_valid_option_closers = html.replace("</option>", "")

        self.assertNotIn("/button>", html_without_valid_button_closers)
        self.assertNotIn("/option>", html_without_valid_option_closers)

    def test_voice_chat_script_calls_speech_endpoint(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("/speak", script)
        self.assertIn("/voice/train", script)
        self.assertIn("trainVoiceModel", script)
        self.assertIn("renderVoiceSamples", script)
        self.assertIn("speakReply", script)

    def test_voice_mode_can_follow_reply_emotion(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('<option value="auto"', html)
        self.assertIn("body.reply.emotion", script)
        self.assertIn('voiceEmotion.value === "auto"', script)
        self.assertIn('replyEmotion || "natural"', script)

    def test_browser_recording_controls_feed_voice_samples(self):
        html = (ROOT / "web" / "index.html").read_text(encoding="utf-8")
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn('id="record-voice-button"', html)
        self.assertIn('id="recording-state"', html)
        self.assertIn("recordedVoiceFiles", script)
        self.assertIn("navigator.mediaDevices.getUserMedia", script)
        self.assertIn("MediaRecorder", script)
        self.assertIn("readCombinedVoiceFiles", script)

    def test_existing_clone_can_upload_additional_voice_samples(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("/voice/samples", script)
        self.assertIn("uploadVoiceSamples", script)
        self.assertIn("clearPendingVoiceSamples", script)

    def test_existing_clone_can_refresh_voice_status(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("/voice/status", script)
        self.assertIn("refreshVoiceStatus", script)
        self.assertIn('method: "GET"', script)

    def test_existing_clone_can_be_loaded_by_id(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("loadExistingClone", script)
        self.assertIn("cloneIdInput.value.trim()", script)
        self.assertIn("fetch(`/api/clones/${encodeURIComponent(cloneId)}`", script)
        self.assertIn("enableChat();", script)

    def test_voice_training_status_auto_polls_until_terminal_state(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("voiceStatusPollTimer", script)
        self.assertIn("scheduleVoiceStatusPoll", script)
        self.assertIn("clearVoiceStatusPoll", script)
        self.assertIn('"queued"', script)
        self.assertIn('"running"', script)
        self.assertIn("setTimeout(refreshVoiceStatus", script)

    def test_ready_voice_training_status_is_successful(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function voiceStatusIsOk(status)", script)
        self.assertIn("function voiceStatusIsError(status)", script)
        self.assertIn('"samples_ready"', script)
        self.assertIn('"ready"', script)
        self.assertIn("voiceStatusIsError(body.voice?.status)", script)

    def test_voice_training_errors_are_marked_in_ui(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")
        css = (ROOT / "web" / "styles.css").read_text(encoding="utf-8")

        for status in ('"pending_backend"', '"pending_adapter"', '"failed"'):
            self.assertIn(status, script)

        self.assertIn('trainingStateEl.classList.toggle("error"', script)
        self.assertIn(".badge.error", css)

    def test_switching_to_text_mode_clears_stale_audio(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("clearSpeechPlayback();", script)
        self.assertIn("function clearSpeechPlayback()", script)
        self.assertIn('audioPlayback.removeAttribute("src")', script)

    def test_voice_mode_treats_unavailable_speech_as_degraded_not_failed(self):
        script = (ROOT / "web" / "app.js").read_text(encoding="utf-8")

        self.assertIn("function speechStatusIsError(status)", script)
        self.assertIn('["error", "failed"].includes(status)', script)
        self.assertIn("setStatus(speech.message || text.speechFailed, speechStatusIsError(speech.status))", script)
