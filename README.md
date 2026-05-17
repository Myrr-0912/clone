# Cyber Clone Lab

本项目是「上传声音文件 + 上传聊天记录 → 生成可聊天的赛博克隆人」的本地 MVP。从 0.2 起，
后端拆分为 **FastAPI JSON 服务**，前端拆分为独立的 **Vue 3 + Vite + TypeScript SPA**，
两者通过 `/api/*` 路由通信，开发期由 Vite 反代避免跨域，生产期由 FastAPI 直接托管打包后的
`frontend/dist`。

## 技术栈

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 后端 HTTP | **FastAPI** + Uvicorn | 16 条 JSON API，session 通过 `cyberclone_session` HttpOnly Cookie |
| 后端数据层 | 文件存储 + 本地向量检索 | 每个用户 / 每个克隆人独立目录 `data/users/{user_id}/clones/{clone_id}/` |
| 文本画像 | 本地规则 fallback + 可选 DeepSeek LLM | `TEXT_TRAINING_BACKEND` 控制；缺 key 自动降级 |
| 文本检索 | 关键词 / 中文 n-gram 本地索引 | 写入 `vector/db.json`，无外部数据库依赖 |
| 语音训练 / 合成 | 本地 VoxCPM HTTP bridge | `VoxCPM-local` 提供，`scripts/run_voxcpm_bridge.py` 包装为 HTTP |
| 前端框架 | **Vue 3.4** + `<script setup>` + Pinia 2 + Vue Router 4 | 完整 SPA 路由、登录态、克隆人 CRUD、文本/语音聊天 |
| 前端构建 | **Vite 5** + TypeScript 5 + vue-tsc | `pnpm dev` 起 5173 端口，`pnpm build` 输出到 `frontend/dist` |
| 前端测试 | **Vitest** + @vue/test-utils + happy-dom | 8 个 spec、26 个测试 |
| 后端测试 | unittest + fastapi.testclient.TestClient | 118 个测试，覆盖领域逻辑与 API |

## 目录结构

```
src/cyberclone/          # 领域逻辑 + FastAPI 适配层
  api/
    main.py              # FastAPI 应用工厂，挂载 router 与 frontend/dist
    paths.py             # 可在测试中 monkeypatch 的路径常量
    deps.py              # current_user / require_admin / get_store 依赖
    conversions.py       # 请求体解码 + profile_to_api 等纯函数
    cookies.py           # session cookie 工具
    routers/             # auth / clones / voice / chat / admin
  auth.py storage.py     # 鉴权 + 多用户克隆人存储
  chat_engine.py llm.py  # 聊天回复（DeepSeek 或本地 fallback）
  voice.py voice_models.py voxcpm_bridge.py
  text_training.py rag.py vector_rag.py vector_store.py
  admin_stats.py resource_layout.py
  web.py                 # 向后兼容入口（封装 uvicorn.run）

frontend/                # Vue 3 SPA
  index.html  vite.config.ts  vitest.config.ts  package.json
  src/
    main.ts  App.vue  env.d.ts  types.ts
    router/index.ts          # vue-router + 全局守卫
    stores/auth.ts clones.ts # Pinia
    api/                     # client / auth / clones / voice / chat / admin
    composables/             # useFileReader / useVoiceRecorder
    views/                   # Login / Register / Workspace / Admin / NotFound
    components/              # MyClonesPanel / ProfilePanel / ChatPanel ...
    assets/styles.css
  tests/                     # vitest spec

data/                    # 本地数据；运行时自动创建
  auth/                  # users.json / sessions.json
  users/{user_id}/clones/{clone_id}/
                         # raw/ profile/ voice/ vector/ status.json

VoxCPM-local/            # VoxCPM 原始 Gradio 服务与权重脚本（详见下文）
scripts/                 # CLI 工具：mock smoke、VoxCPM bridge、模型控制
docs/                    # 设计文档 / 子需求 spec
tests/                   # Python 测试套件
```

## 一、安装依赖

### 1. Python（后端）

需要 Python 3.10+。

```powershell
python -m pip install -e .
# 或者只装运行所需的依赖（不安装本项目本身）
python -m pip install fastapi "uvicorn[standard]" pydantic
```

### 2. Node（前端）

需要 Node 18+。

```powershell
cd frontend
npm install
# 或 pnpm install / yarn install
```

## 二、运行测试

### 后端

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
python -m unittest discover -s tests -v
```

若机器没有 `python`，可以用 Codex 自带运行时：

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
& "C:\Users\myrr\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests -v
```

### 前端

```powershell
cd frontend
npm test            # 一次性跑全部 vitest
npm run test:watch  # 监听模式
npm run build       # vue-tsc 类型检查 + Vite 打包
```

## 三、本地开发模式（前后端分离）

两个终端各跑一个进程，前端通过 Vite 反代 `/api/*` 调后端，**无 CORS 问题**。

终端 A —— 启动后端：

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
$env:NO_PROXY="127.0.0.1,localhost,::1"
$env:no_proxy="127.0.0.1,localhost,::1"
python -m cyberclone.api --port 8787
```

终端 B —— 启动前端 dev server：

```powershell
cd frontend
npm run dev
```

浏览器打开：

```text
http://127.0.0.1:5173
```

第一次进入会被路由守卫导向 `/login`。**默认管理员账号** 是 `admin / admin`，
可登录后查看 `/admin` 资源统计。**普通用户** 通过 `/register` 注册即可使用工作台。

## 四、生产 / 一体化运行

```powershell
cd frontend
npm run build     # 产物到 frontend/dist

cd ..
$env:PYTHONPATH="D:\vscode\clone\src"
python -m cyberclone.api --port 8787
# 或保留旧入口：python -m cyberclone.web --port 8787
```

FastAPI 在生产模式下会把 `frontend/dist` 挂到 `/`：

- `/` 与未命中 `/api/*` 的所有 GET 请求都 fallback 到 `index.html`，由 vue-router 处理
- `/assets/*` 由 FastAPI 直接送回 Vite 打包出的静态文件
- `/api/*` 仍然是 JSON API

打开：

```text
http://127.0.0.1:8787
```

## 五、安装与部署 VoxCPM 语音模型

VoxCPM 适合接在 `src/cyberclone/voice.py` 后面，负责声音克隆训练和 TTS 推理。本仓库的 `VoxCPM-local`
目录保留了 VoxCPM 的 Gradio 服务与模型验证脚本；为了对接到 FastAPI，我们额外提供一个轻量 HTTP bridge
（`src/cyberclone/voxcpm_bridge.py` + `scripts/run_voxcpm_bridge.py`），把 VoxCPM 的 reference voice
就绪状态映射成 `POST /train`，把本地推理映射成 `POST /speak`。

### 1. 准备 VoxCPM 运行环境

```powershell
# 在你想运行 VoxCPM 的目录（建议独立 venv）
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r VoxCPM-local\requirements.txt
```

下载 VoxCPM 权重文件（按 `VoxCPM-local` 自带文档的指引），把路径配置在 `.env`：

```ini
VOXCPM_MODEL_PATH=D:\vscode\clone\VoxCPM-local\weights\voxcpm.pt
VOXCPM_ZIPENHANCER_MODEL_PATH=D:\vscode\clone\VoxCPM-local\weights\zipenhancer.pt
VOXCPM_BRIDGE_ENABLE_DENOISER=false   # 没装 zip-enhancer 时设 false
VOXCPM_BRIDGE_OPTIMIZE=false
VOXCPM_BRIDGE_DEVICE=auto             # cpu / cuda:0 / cuda:1
```

### 2. 启动 VoxCPM HTTP bridge

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
python scripts\run_voxcpm_bridge.py
# 默认监听 127.0.0.1:8810；日志写入 logs/voxcpm-bridge.log
```

启动成功后会出现 `POST /train`、`POST /speak`、`GET /healthz` 三个端点（详见
`docs/voxcpm-http-bridge.md`）。

### 3. 把主服务指向 bridge

在仓库根目录 `.env` 中：

```ini
VOICE_TRAINING_BACKEND=voxcpm
VOICE_TRAINING_URL=http://127.0.0.1:8810/train

VOICE_TTS_BACKEND=voxcpm
VOICE_TTS_URL=http://127.0.0.1:8810/speak

# 如果 bridge 与主服务不在同一台机器、无法读取本机 samplePaths：
VOICE_TRAINING_INCLUDE_AUDIO=true
VOICE_TTS_INCLUDE_REFERENCE_AUDIO=true
```

主服务重启后即可在前端「训练音色」「语音聊天」中使用 VoxCPM。`scripts/run_voice_model_control.py`
还提供了一个独立的控制面板，可启停 bridge 并切换设备 / 优化选项。

### 4. 不部署 VoxCPM 时的退化

- 留空 `VOICE_TTS_BACKEND` 与 `VOICE_TRAINING_BACKEND`：上传/聊天功能正常，前端会显示「未配置」提示
- 设 `VOICE_TTS_BACKEND=mock` / `VOICE_TRAINING_BACKEND=mock`：返回本地占位 WAV 与就绪状态，
  便于验证整链路（见下一节 **Mock 端到端验证**）

## 六、Mock 端到端验证

不依赖真实 LLM、VoxCPM 或外部语音 API key 时，可以用 mock 后端跑完整流程：

```powershell
$env:PYTHONPATH="D:\vscode\clone\src"
$env:LLM_BACKEND="local"
$env:VOICE_TRAINING_BACKEND="mock"
$env:VOICE_TTS_BACKEND="mock"
python -m cyberclone.api --port 8787
```

在另一个终端启动前端 `npm run dev` 后，浏览器打开 `http://127.0.0.1:5173`：

1. 注册或登录账号，进入工作台 `/app`
2. 输入克隆对象名称、粘贴或导入一段 `Target: ...` 格式的聊天文本
3. 上传多段**语音样本**，或点击「录制语音样本」录一段麦克风音频
4. 勾选授权确认后点击「开始训练」，确认样本列表、画像和聊天区已更新
5. 在「追加语音样本与训练」面板点击「**训练音色**」，mock 训练会把音色状态标记为 ready
6. 在聊天测试区先用「文本」模式发消息，确认能收到纯文本回复
7. 切换到「语音」模式（这是**双模式聊天**），选择「自动」或具体情绪后发消息，
   确认播放器出现并自动播放 mock WAV

如果去掉 `VOICE_TRAINING_BACKEND=mock` 或 `VOICE_TTS_BACKEND=mock`，界面应保留文本聊天能力，
并在训练状态或语音播放位置显示清晰的未配置 / 降级提示。

## 七、聊天画像分层

参考 ex-skill 的思路，每个 clone 会同时沉淀以下文件：

- `profile/persona.md` —— 5 层 Persona（硬规则、身份、说话风格、情感模式、关系行为）
- `profile/memory.md` —— Relationship Memory（关系概览、时间线、共同经历、争吵 / 甜蜜模式等）
- `profile/style.md` —— 口头禅、语气词、表情习惯、平均消息长度
- `profile/**rules.md**` —— 硬规则与边界
- `profile/corrections.md` —— 用户在聊天中用 `ta 不会这样说，不要...` 给出的纠正

聊天时，服务端会把 `Retrieved Chat Evidence` 注入 LLM system prompt，要求优先参考真实聊天
片段中的事实、称呼、语气与表达节奏，并禁止编造片段之外的私人经历。

## 八、配置参考

`.env.example` 列出全部占位配置。核心变量：

- `DEEPSEEK_API_KEY`：可选；配置后用于文本训练画像与 LLM 聊天回复
- `LLM_BACKEND=local`：可选；强制本地确定性聊天，适合本地语音链路验证
- `TEXT_TRAINING_BACKEND=llm` / `local`：可选；强制走 LLM 或本地规则
- `VOICE_TTS_BACKEND` / `VOICE_TRAINING_BACKEND`：留空 / mock / http / voxcpm
- `VOICE_TTS_INCLUDE_REFERENCE_AUDIO=true` / `VOICE_TRAINING_INCLUDE_AUDIO=true`：
  远端 bridge 无法读取本机 `referenceAudioPath` / `samplePaths` 时，把样本以 data URL 一并发送
- `CYBERCLONE_DEV_CORS=1`：开发期手动开启 CORS（默认关，Vite 反代已规避跨域）

## 九、下一步

- 引入 embedding 检索替换当前的本地关键词索引
- 将 VoxCPM 推理与 FastAPI 部署到同一容器，简化部署
- 用 vitest + Playwright 补 E2E，使前端关键链路有可回放的浏览器测试
- 把根目录历史遗留的 `chatService.ts` / `ExportPage.tsx` / `exportService.ts` 清理或归档
