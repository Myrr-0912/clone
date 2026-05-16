# Cyber Clone MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local MVP where a user uploads a voice file and chat log, receives a generated cyber-clone profile, and can chat with the clone through a browser.

**Architecture:** Use a dependency-light Python application with a small stdlib HTTP server and browser frontend. Core behavior lives in focused Python modules: chat parsing, persona extraction, clone storage, voice-job status, and a deterministic local chat engine that can later be swapped for an LLM-backed engine.

**Tech Stack:** Python 3.10+ standard library, `unittest`, static HTML/CSS/JS, optional future adapters for VoxCPM and ex-skill prompt logic.

---

### Task 1: Core Model And Chat Log Parsing

**Files:**
- Create: `src/cyberclone/models.py`
- Create: `src/cyberclone/chatlog.py`
- Create: `tests/test_chatlog.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from cyberclone.chatlog import parse_chat_log


class ChatLogTests(unittest.TestCase):
    def test_parses_wechat_style_lines(self):
        raw = """2026-01-01 10:00 Alice: 你在干嘛
2026-01-01 10:01 Bob: 刚吃完饭 哈哈哈
2026-01-01 10:02 Bob: 等下去健身"""

        messages = parse_chat_log(raw, target_name="Bob")

        self.assertEqual(len(messages), 3)
        self.assertEqual(messages[1].speaker, "Bob")
        self.assertEqual(messages[1].text, "刚吃完饭 哈哈哈")
        self.assertTrue(messages[1].is_target)

    def test_parses_json_messages(self):
        raw = '[{"sender":"Me","content":"早"},{"sender":"Clone","content":"早啊"}]'

        messages = parse_chat_log(raw, target_name="Clone")

        self.assertEqual([m.text for m in messages], ["早", "早啊"])
        self.assertFalse(messages[0].is_target)
        self.assertTrue(messages[1].is_target)
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_chatlog -v`

Expected: import failure because `cyberclone.chatlog` does not exist.

- [ ] **Step 3: Implement parser**

Create dataclasses for parsed messages and support JSON arrays plus common `time speaker: text` lines.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m unittest tests.test_chatlog -v`

Expected: 2 tests pass.

### Task 2: Persona And Memory Distillation

**Files:**
- Create: `src/cyberclone/persona.py`
- Create: `tests/test_persona.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from cyberclone.chatlog import ChatMessage
from cyberclone.persona import build_clone_profile


class PersonaTests(unittest.TestCase):
    def test_builds_style_and_memory_from_target_messages(self):
        messages = [
            ChatMessage("Me", "你在干嘛", False, None),
            ChatMessage("Target", "刚吃完饭 哈哈哈", True, None),
            ChatMessage("Target", "等下去健身 哈哈哈", True, None),
        ]

        profile = build_clone_profile("Target", messages)

        self.assertEqual(profile.name, "Target")
        self.assertIn("哈哈哈", profile.style.catchphrases)
        self.assertIn("健身", profile.memory.key_topics)
        self.assertGreater(profile.style.average_length, 0)
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_persona -v`

Expected: import failure because `cyberclone.persona` does not exist.

- [ ] **Step 3: Implement persona distillation**

Extract target-only style signals: common catchphrases, punctuation habits, average message length, and simple key topics.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m unittest tests.test_persona -v`

Expected: persona tests pass.

### Task 3: Clone Storage And Training Job Snapshot

**Files:**
- Create: `src/cyberclone/storage.py`
- Create: `src/cyberclone/voice.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write failing tests**

```python
import tempfile
import unittest
from pathlib import Path

from cyberclone.storage import CloneStore


class StorageTests(unittest.TestCase):
    def test_creates_clone_with_profile_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = CloneStore(Path(tmp))
            clone = store.create_clone(
                target_name="Target",
                chat_text="Target: 哈哈哈 我来了",
                voice_filename="voice.wav",
                voice_bytes=b"RIFF",
            )

            clone_dir = Path(tmp) / clone.clone_id
            self.assertTrue((clone_dir / "profile" / "persona.md").exists())
            self.assertTrue((clone_dir / "voice" / "voice.wav").exists())
            self.assertEqual(store.load_clone(clone.clone_id).name, "Target")
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_storage -v`

Expected: import failure because `cyberclone.storage` does not exist.

- [ ] **Step 3: Implement storage and voice status**

Create clone directories, save raw inputs, write profile markdown files, and record a voice training status JSON with `pending_adapter` for VoxCPM.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m unittest tests.test_storage -v`

Expected: storage tests pass.

### Task 4: Local Chat Engine

**Files:**
- Create: `src/cyberclone/chat_engine.py`
- Create: `tests/test_chat_engine.py`

- [ ] **Step 1: Write failing tests**

```python
import unittest

from cyberclone.chat_engine import LocalCloneChatEngine
from cyberclone.models import CloneMemory, CloneProfile, CloneStyle


class ChatEngineTests(unittest.TestCase):
    def test_reply_uses_clone_style(self):
        profile = CloneProfile(
            clone_id="abc",
            name="Target",
            style=CloneStyle(catchphrases=["哈哈哈"], punctuation=[""], average_length=6),
            memory=CloneMemory(key_topics=["健身"], summary="喜欢聊健身"),
            source_stats={"target_messages": 2},
        )

        reply = LocalCloneChatEngine().reply(profile, "你在干嘛")

        self.assertIn("哈哈哈", reply.text)
        self.assertEqual(reply.clone_id, "abc")
```

- [ ] **Step 2: Run tests and verify they fail**

Run: `python -m unittest tests.test_chat_engine -v`

Expected: import failure because `cyberclone.chat_engine` does not exist.

- [ ] **Step 3: Implement deterministic local reply**

Generate a short style-aware reply that uses catchphrases and key topics. Keep it explicitly as local fallback, not a claim of true LLM imitation.

- [ ] **Step 4: Run tests and verify they pass**

Run: `python -m unittest tests.test_chat_engine -v`

Expected: chat engine tests pass.

### Task 5: Browser MVP

**Files:**
- Create: `src/cyberclone/web.py`
- Create: `web/index.html`
- Create: `web/styles.css`
- Create: `web/app.js`
- Create: `README.md`

- [ ] **Step 1: Implement API and frontend**

Expose:
- `GET /`
- `GET /api/health`
- `POST /api/clones`
- `GET /api/clones/{clone_id}`
- `POST /api/clones/{clone_id}/chat`

The frontend should show two upload controls, a target-name input, training status, profile preview, and a chat panel.

- [ ] **Step 2: Run full tests**

Run: `python -m unittest discover -s tests -v`

Expected: all tests pass.

- [ ] **Step 3: Start local server**

Run: `python -m cyberclone.web --port 8787`

Expected: server prints `http://localhost:8787`.

---

## Self-Review

- Spec coverage: The MVP covers upload, profile distillation, voice-job placeholder, and chat. Real VoxCPM training and LLM inference are intentionally adapter points for the next iteration.
- Placeholder scan: The implementation plan avoids unresolved code placeholders in test steps; Task 5 is UI/API assembly after core tests are green.
- Type consistency: `CloneProfile`, `CloneStyle`, `CloneMemory`, and `CloneStore` are shared across planned tests and modules.
