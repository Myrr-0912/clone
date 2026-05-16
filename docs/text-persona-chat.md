# Text Persona Chat

The pure-text chat path follows the ex-skill-style split between remembered
context and persona constraints:

- `Part A - Relationship Memory` carries extracted topics and the target-message
  summary.
- `Part B - Persona` carries hard rules, identity, speech style, emotional
  patterns, and relationship behavior.

`src/cyberclone/persona.py` writes the same structure to
`data/clones/{clone_id}/profile/persona.md` and exposes
`profile_to_system_prompt()` for LLM-backed chat. `src/cyberclone/llm.py` uses
that prompt when `DEEPSEEK_API_KEY` or `LLM_API_KEY` is configured.

Without an API key, `LocalCloneChatEngine` remains the deterministic text
fallback. That keeps the browser chat usable for local verification while
making the LLM slot explicit.

Minimum verification:

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  -m unittest tests.test_persona tests.test_llm -v
```
