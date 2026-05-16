# Cyber Clone MVP

本项目是“上传声音文件 + 上传聊天记录 → 生成可聊天的赛博克隆人”的本地 MVP。

当前版本已经完成：

- 聊天记录解析：支持 `Speaker: text`、带时间戳文本、JSON 消息列表。
- 画像沉淀：提取口头禅、常聊话题、平均消息长度和记忆摘要。
- 克隆存储：保存原始聊天、声音样本、画像 Markdown、结构化 JSON。
- 规则拆分：参考 ex-skill 的分层思路，为每个 clone 写出 `persona.md`、`memory.md`、`style.md`、`rules.md` 和 `corrections.md`。
- 本地聊天：用确定性规则模拟画像效果，后续可替换成 LLM。
- VoxCPM 预留：声音文件已进入 `voice` 目录，并生成可扩展的训练/合成适配状态。
- 语音训练状态：上传多段语音样本后，可触发独立的音色训练状态接口；未配置训练后端时会明确显示降级/错误原因。
- 追加语音样本：clone 创建后仍可继续上传或录制样本，样本列表和训练状态会同步刷新。
- 双模式聊天：前端支持文本聊天和语音聊天。语音模式会先生成文本回复，再调用语音合成后端播放音频；未配置语音后端时会保留清晰降级提示。

## 运行测试

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
python -m unittest discover -s tests -v
```

如果系统没有 `python` 命令，可以使用 Codex 自带运行时：

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

## 启动本地服务

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
$env:NO_PROXY="127.0.0.1,localhost,::1"
$env:no_proxy="127.0.0.1,localhost,::1"
python -m cyberclone.web --port 8787
```

或直接用项目自带启动脚本：

```powershell
python scripts/run_server.py --port 8787
```

打开：

```text
http://127.0.0.1:8787
```

## Mock 端到端验证

没有真实 LLM、VoxCPM 或外部语音 API key 时，可以用 mock 后端跑完整流程：

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
$env:LLM_BACKEND="local"
$env:VOICE_TRAINING_BACKEND="mock"
$env:VOICE_TTS_BACKEND="mock"
python -m cyberclone.web --port 8787
```

浏览器打开 `http://127.0.0.1:8787` 后按以下步骤验证：

1. 输入克隆对象名称，粘贴或导入一段 `Target: ...` 格式的聊天文本。
2. 上传多段语音样本，或点击“录制语音样本”录一段麦克风音频。
3. 勾选授权确认后点击“开始训练”，确认样本列表、画像和聊天区已更新。
4. 点击“训练音色”，mock 训练会把音色状态标记为 ready。
5. 在聊天测试区先用“文本”模式发消息，确认能收到纯文本回复。
6. 切换到“语音”模式，选择“自动”或具体情绪后发消息，确认播放器出现并播放 mock WAV。

如果去掉 `VOICE_TRAINING_BACKEND=mock` 或 `VOICE_TTS_BACKEND=mock`，界面应保留文本聊天能力，并在训练状态或语音播放位置显示清晰的未配置/降级提示。

## 聊天与语音模型配置

纯文本聊天模式参考了 ex-skill 的拆分思路：先从聊天记录沉淀 `persona / memory / style / rules`，运行时再把这些信号注入聊天回复。`rules.md` 会进一步记录回复节奏、常用称呼、安慰/冲突模式、关系互动和忙碌边界表达；当前本地 fallback 是确定性规则；配置 LLM 后会改用 OpenAI-compatible chat completions。

文本聊天支持轻量纠正层：在聊天框输入类似 `ta不会这样说，不要再说哈哈哈` 的反馈时，服务端会把纠正追加到 `data/clones/{clone_id}/profile/corrections.md` 和结构化 profile。后续 LLM prompt 会包含 `Part C - Corrections`；本地 fallback 也会避开已被明确否定的口头禅。

语音聊天模式使用两步流程：

1. `POST /api/clones/{clone_id}/chat` 生成文本回复。
2. `POST /api/clones/{clone_id}/speak` 将回复文本、情绪和第一段参考语音样本交给语音后端。

音色训练是独立动作：上传并创建 clone 后，前端的“训练音色”按钮会调用 `POST /api/clones/{clone_id}/voice/train`。未配置训练后端时只保留样本和状态提示；设置 `VOICE_TRAINING_BACKEND=mock` 可验证完整状态更新链路。

如果 clone 已经创建，可以继续选择本地音频或录制麦克风样本，然后点击“保存样本”。前端会调用：

```text
POST /api/clones/{clone_id}/voice/samples
```

请求体：

```json
{
  "voiceFiles": [
    {"name": "new-sample.wav", "data": "data:audio/wav;base64,..."}
  ]
}
```

成功后服务端会把样本追加到 `data/clones/{clone_id}/voice/`，重建 `samples_ready` 状态，并要求再次点击“训练音色”来刷新外部语音模型。

`.env.example` 提供了全部占位配置。关键变量：

- `DEEPSEEK_API_KEY`：可选；留空时使用本地文本 fallback。
- `LLM_BACKEND=local`：可选；即使 `.env` 中保留真实 LLM key，也强制使用本地确定性文本聊天，适合本地语音链路验证。
- `VOICE_TTS_BACKEND`：可选；留空时语音模式显示未配置提示。
- `VOICE_TTS_BACKEND=mock`：生成一段本地 WAV 测试音，用于验证浏览器播放链路。
- `VOICE_TTS_BACKEND=http` / `voxcpm-http` / `voxcpm`：调用 `VOICE_TTS_URL` 或 `VOXCPM_TTS_URL`。
- `VOICE_TTS_API_KEY`：可选；配置后会以 Bearer token 发送给语音后端。
- `VOICE_TTS_INCLUDE_REFERENCE_AUDIO=true`：可选；远端语音合成服务无法读取本机 `referenceAudioPath` 时，把第一段参考音频以 `referenceAudioFile.data` 的 data URL 一并发送。
- `VOICE_TRAINING_BACKEND=mock`：可选；把已上传样本标记为本地验证用的 ready 模型。
- `VOICE_TRAINING_BACKEND=http` / `voxcpm-http` / `voxcpm`：调用 `VOICE_TRAINING_URL` 或 `VOXCPM_TRAINING_URL`。
- `VOICE_TRAINING_API_KEY`：可选；配置后会以 Bearer token 发送给训练后端。
- `VOICE_TRAINING_INCLUDE_AUDIO=true`：可选；远端训练服务无法读取本机 `samplePaths` 时，把样本以 `sampleFiles[].data` 的 data URL 一并发送。

HTTP 语音训练后端需要接收 JSON：

```json
{
  "cloneId": "abc123",
  "voiceName": "Target",
  "samplePaths": ["D:\\vscode\\clone\\data\\clones\\...\\voice\\sample.wav"],
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

`sampleFiles` 只会在 `VOICE_TRAINING_INCLUDE_AUDIO=true` 时出现；VoxCPM bridge
默认只需要 `samplePaths`，但在远端/无共享磁盘部署时也能接收 `sampleFiles` 并优先落盘使用。

并返回：

```json
{"status": "ready", "message": "Voice model ready", "modelId": "voice-model-abc123", "jobId": "job-1"}
```

HTTP 语音后端需要接收 JSON：

```json
{
  "text": "模型回复文本",
  "emotion": "warm",
  "cloneId": "abc123",
  "voiceName": "Target",
  "referenceAudioPath": "D:\\vscode\\clone\\data\\clones\\...\\voice\\sample.wav",
  "referenceAudioFile": {
    "name": "sample.wav",
    "contentType": "audio/wav",
    "data": "data:audio/wav;base64,..."
  }
}
```

`referenceAudioFile` 只会在 `VOICE_TTS_INCLUDE_REFERENCE_AUDIO=true` 且存在参考样本时出现；VoxCPM bridge
默认只需要 `referenceAudioPath`，但在远端/无共享磁盘部署时也能接收 `referenceAudioFile` 并优先落盘使用。

并返回以下任一格式：

```json
{"audioDataUrl": "data:audio/wav;base64,...", "contentType": "audio/wav"}
```

或：

```json
{"audioBase64": "...", "contentType": "audio/wav"}
```

本仓库的 `VoxCPM-local` 目录保留了本地 VoxCPM Gradio 服务和模型验证脚本；如需接入生产推理，建议在其外层加一个兼容上述 HTTP 契约的轻量包装服务。

本轮已补充轻量 HTTP bridge：`src/cyberclone/voxcpm_bridge.py` 和
`scripts/run_voxcpm_bridge.py`。它把 `POST /train` 映射成 VoxCPM reference
voice 就绪状态，把 `POST /speak` 映射成本地 VoxCPM 语音合成，并返回主应用
已支持的 `audioBase64` 响应。启动和配置步骤见
`docs/voxcpm-http-bridge.md`。

## 下一步

VoxCPM 适合接在 `src/cyberclone/voice.py` 后面，负责声音克隆训练和 TTS 推理。
ex-skill 的思想还可以继续扩展 `src/cyberclone/persona.py`，把更多训练材料沉淀成更细的语气规则、关系记忆和对话行为约束。
