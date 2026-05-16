# Mock Voice Smoke Validation

Use this path when validating the latest local code without external model
services. It forces deterministic text chat and mock voice backends, so no API key
or GPU worker is required.

## Environment

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
$env:NO_PROXY="127.0.0.1,localhost,::1"
$env:no_proxy="127.0.0.1,localhost,::1"
$env:LLM_BACKEND="local"
$env:VOICE_TRAINING_BACKEND="mock"
$env:VOICE_TTS_BACKEND="mock"
```

## API Smoke Path

The repeatable command is:

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" scripts/mock_api_smoke.py --start-server --port 8792
```

Use a different port if `8792` is already occupied. The script starts
`cyberclone.web`, forces `LLM_BACKEND=local`,
`VOICE_TRAINING_BACKEND=mock`, and `VOICE_TTS_BACKEND=mock`, then verifies
health, clone creation, post-create voice sample upload, mock voice training,
text chat, and mock WAV synthesis.

For manual validation or debugging, use the equivalent steps below.

Start the server:

```powershell
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m cyberclone.web --port 8787
```

Then verify this sequence:

1. `GET /api/health` returns `{"ok": true}`.
2. `POST /api/clones` with `targetName`, `chatText`, and one or more
   `voiceFiles` returns `201` with a `cloneId`.
3. `POST /api/clones/{cloneId}/voice/samples` accepts another `voiceFiles`
   payload and returns `sample_count` of at least `2`.
4. `POST /api/clones/{cloneId}/voice/train` returns voice status `ready` and
   adapter `mock`.
5. `GET /api/clones/{cloneId}/voice/status` returns the persisted voice status.
6. `POST /api/clones/{cloneId}/chat` returns non-empty reply text.
7. `POST /api/clones/{cloneId}/speak` returns speech backend `mock` and an
   `audioDataUrl` starting with `data:audio/wav;base64,`.

Run the regression suite after the smoke path:

```powershell
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

## Browser Automation Notes

On this Windows host, PowerShell may resolve `npm`/`npx` to blocked `.ps1`
shims. Use `npm.cmd` or `npx.cmd` when a Node CLI is already installed.

The current host also has a duplicate `Path`/`PATH` environment issue that makes
PowerShell `Start-Process` fail. Python `subprocess` can still launch the local
server for API validation.

Headless Chrome needed `--headless --single-process --disable-gpu` to expose the
DevTools endpoint, but the page target was not stable enough for a full browser
smoke run in this environment. Treat the API smoke path above as the current
repeatable verification until the local browser runner is fixed.
