# VoxCPM Standalone Control Page

This page is separate from the Cyber Clone web app. It starts and stops the
local VoxCPM HTTP bridge process so GPU memory can be released when the queue
backs up or when voice mode is not needed.

## Start The Control Page

```powershell
$env:PYTHONPATH="D:\vscode\clone\src;D:\vscode\clone"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  "D:\vscode\clone\scripts\run_voice_model_control.py" `
  --host 127.0.0.1 `
  --port 8820
```

Open:

```text
http://127.0.0.1:8820
```

The control page starts the bridge with `scripts/run_voxcpm_bridge.py` and
writes:

- PID state: `data/voice-model-control/voxcpm-bridge.json`
- Bridge log: `logs/voxcpm-bridge.log`

## Optional Configuration

Set these values in `.env` when the defaults do not match your machine:

```dotenv
VOXCPM_BRIDGE_PYTHON=D:\vscode\clone\VoxCPM-local\.venv\Scripts\python.exe
VOXCPM_BRIDGE_HOST=127.0.0.1
VOXCPM_BRIDGE_PORT=8810
VOXCPM_BRIDGE_DEVICE=auto
VOXCPM_MODEL_PATH=D:\vscode\clone\VoxCPM-local\models\models--openbmb--VoxCPM2\snapshots\bffb3df5a29440629464e5e839f4d214c8714c3d
VOXCPM_BRIDGE_LOG_PATH=logs\voxcpm-bridge.log
```

Optional tuning:

```dotenv
VOXCPM_BRIDGE_OPTIMIZE=false
VOXCPM_BRIDGE_ENABLE_DENOISER=false
VOXCPM_ZIPENHANCER_MODEL_PATH=
VOXCPM_BRIDGE_HEALTH_TIMEOUT_SECONDS=1.5
VOXCPM_BRIDGE_STARTUP_TIMEOUT_SECONDS=12
```

The main app should still point at the same bridge port:

```dotenv
VOICE_TRAINING_BACKEND=voxcpm
VOICE_TRAINING_URL=http://127.0.0.1:8810/train
VOICE_TTS_BACKEND=voxcpm
VOICE_TTS_URL=http://127.0.0.1:8810/speak
```

If a bridge is already running on that port but was not started by the control
page, the page reports it as external. In that case, stop the manually started
process first, then start it from the page so the control page owns the PID.
