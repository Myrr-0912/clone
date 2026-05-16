# VoxCPM HTTP Bridge

`src/cyberclone/voice.py` already calls an OpenAI-style HTTP contract for voice
training and speech synthesis. The bridge in `src/cyberclone/voxcpm_bridge.py`
adapts that contract to the local `VoxCPM-local` model.

VoxCPM is reference-conditioned TTS in this MVP, not a long-running fine-tune
job. The bridge therefore treats `/train` as "register these uploaded voice
samples as the reference voice" and returns a ready model id. `/speak` then uses
the first sample path as `reference_wav_path` and maps chat emotion to a Chinese
voice-control prompt. If the main app sends embedded `sampleFiles[]` or
`referenceAudioFile` data URLs, the bridge writes them under the system temp
directory (`cyberclone-voxcpm-bridge/<cloneId>/...`) and passes the saved WAV
path to VoxCPM. This keeps remote bridge deployments working when the bridge
cannot read the main app's local disk paths.

## Start The Bridge

Run it with the VoxCPM virtual environment so the `voxcpm`, `torch`, and
`soundfile` dependencies are available:

```powershell
& "D:\vscode\clone\VoxCPM-local\.venv\Scripts\python.exe" `
  "D:\vscode\clone\scripts\run_voxcpm_bridge.py" `
  --host 127.0.0.1 `
  --port 8810 `
  --device auto `
  --model-path "D:\vscode\clone\VoxCPM-local\models\models--openbmb--VoxCPM2\snapshots\bffb3df5a29440629464e5e839f4d214c8714c3d"
```

Health check:

```powershell
Invoke-RestMethod http://127.0.0.1:8810/health
```

## Connect The Main App

Set these values in `D:\vscode\clone\.env`:

```dotenv
VOICE_TRAINING_BACKEND=voxcpm
VOICE_TRAINING_URL=http://127.0.0.1:8810/train
VOICE_TTS_BACKEND=voxcpm
VOICE_TTS_URL=http://127.0.0.1:8810/speak
VOICE_TTS_TIMEOUT_SECONDS=180
VOICE_TRAINING_TIMEOUT_SECONDS=30
# Optional controls forwarded in every speech synthesis request.
VOICE_TTS_CONTROL_PROMPT_WARM=gentle, close, patient voice
VOICE_TTS_CFG_VALUE=2.0
VOICE_TTS_INFERENCE_STEPS=4
VOICE_TTS_NORMALIZE=false
# Leave false for the local bridge; set true only for remote TTS services that
# cannot read the local referenceAudioPath.
VOICE_TTS_INCLUDE_REFERENCE_AUDIO=false
```

Loopback URLs such as `127.0.0.1`, `localhost`, and `::1` are sent without
system HTTP proxy settings, so a local bridge keeps working on machines with a
global proxy configured.

Then start the Cyber Clone web app:

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" `
  -m cyberclone.web --port 8787
```

Upload one or more voice samples, create the clone, click "训练音色", switch to
voice chat, choose an emotion, and send a message. The main app will call
`/api/clones/{clone_id}/chat` first and `/api/clones/{clone_id}/speak` second;
the second call is forwarded to the bridge and returns `audioBase64`.

## Bridge Endpoints

`POST /train` accepts:

```json
{
  "cloneId": "abc123",
  "voiceName": "Target",
  "samplePaths": ["D:\\vscode\\clone\\data\\clones\\abc123\\voice\\sample.wav"],
  "sampleFilenames": ["sample.wav"],
  "sampleFiles": [
    {
      "name": "sample.wav",
      "contentType": "audio/wav",
      "data": "data:audio/wav;base64,..."
    }
  ]
}
```

`sampleFiles` is optional. When present, the bridge stores the embedded files
locally and prefers those stored paths over any unshared `samplePaths` values.

It returns:

```json
{
  "status": "ready",
  "adapter": "voxcpm-reference",
  "modelId": "voxcpm-reference-abc123",
  "jobId": "local-reference-abc123",
  "sampleCount": 1,
  "sampleFilenames": ["sample.wav"],
  "samplePaths": ["C:\\Users\\...\\AppData\\Local\\Temp\\cyberclone-voxcpm-bridge\\abc123\\training\\sample.wav"]
}
```

`POST /speak` accepts the same payload emitted by the main app:

```json
{
  "text": "模型回复文本",
  "emotion": "warm",
  "cloneId": "abc123",
  "voiceName": "Target",
  "referenceAudioPath": "D:\\vscode\\clone\\data\\clones\\abc123\\voice\\sample.wav",
  "modelId": "voxcpm-reference-abc123",
  "jobId": "local-reference-abc123",
  "voiceStatus": "ready",
  "voiceAdapter": "voxcpm-reference",
  "sampleFilenames": ["sample.wav"],
  "sampleCount": 1,
  "referenceAudioFile": {
    "name": "sample.wav",
    "contentType": "audio/wav",
    "data": "data:audio/wav;base64,..."
  },
  "controlPrompt": "gentle, close, patient voice",
  "cfgValue": 2.0,
  "inferenceSteps": 4,
  "normalize": false
}
```

`referenceAudioFile` is optional. If present, the bridge prefers it over
`referenceAudioPath`, stores it locally, and sends that stored path into VoxCPM.

It returns:

```json
{
  "status": "ok",
  "audioBase64": "...",
  "contentType": "audio/wav",
  "emotion": "warm"
}
```

Optional request fields for advanced tuning: `controlPrompt`, `promptText`,
`cfgValue`, `inferenceSteps`, and `normalize`. The main app can now populate
`controlPrompt` from `VOICE_TTS_CONTROL_PROMPT` or a per-emotion override such as
`VOICE_TTS_CONTROL_PROMPT_WARM`, and can forward `VOICE_TTS_CFG_VALUE`,
`VOICE_TTS_INFERENCE_STEPS`, and `VOICE_TTS_NORMALIZE` to the bridge.

For remote TTS services that cannot read local disk paths, set
`VOICE_TTS_INCLUDE_REFERENCE_AUDIO=true`; the main app will add a
`referenceAudioFile` object with `name`, `contentType`, and base64 data URL.
