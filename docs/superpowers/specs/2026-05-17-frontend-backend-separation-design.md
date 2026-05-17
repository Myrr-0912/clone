# 前后端分离改造设计

> 状态：草案，待审阅。

## 目标

把当前由 `src/cyberclone/web.py`（Python `http.server`）同时承担 API + 静态文件服务的单体结构，拆分为：

- **后端**：纯 JSON API 服务（FastAPI + uvicorn）
- **前端**：独立 Vue 3 + Vite + TypeScript SPA，可独立 dev / build

前端代码全部从零重写，与现有 1498 行 vanilla JS SPA 一一对齐功能。Python 端的领域逻辑（`auth.py` / `storage.py` / `chat_engine.py` / `voice.py` / `text_training.py` / `rag.py` / `vector_store.py` / `admin_stats.py` 等）**完整保留并复用**，只换 HTTP 适配层。

## 改造范围

### 后端

新增 `src/cyberclone/api/` 包，按职责划分 router：

```
src/cyberclone/api/
├── __init__.py
├── main.py          # FastAPI 应用工厂、CORS、生命周期、静态挂载
├── deps.py          # current_user / require_admin / get_store 依赖
├── schemas.py       # Pydantic 请求/响应模型
└── routers/
    ├── __init__.py
    ├── auth.py      # /api/auth/{me,register,login,logout}
    ├── clones.py    # /api/clones[/...]  CRUD + 列表 + 详情
    ├── voice.py     # /api/clones/{id}/voice/{status,samples,train}
    ├── chat.py      # /api/clones/{id}/{chat,speak}
    └── admin.py     # /api/admin/vector-dbs
```

`src/cyberclone/web.py` 改为薄薄一层 entry point：调用 `cyberclone.api.main:create_app()` 并通过 `uvicorn.run(...)` 启动，保留 `python -m cyberclone.web --port 8787` 兼容性。同时新增 `python -m cyberclone.api` 入口。

API URL **保持不变**，仍然是当前 16 条路由：

- `GET  /api/health`
- `GET  /api/auth/me`
- `POST /api/auth/{register,login,logout}`
- `GET  /api/clones`、`POST /api/clones`
- `GET/PUT/DELETE /api/clones/{id}`
- `GET  /api/clones/{id}/voice/status`
- `POST /api/clones/{id}/voice/{samples,train}`
- `POST /api/clones/{id}/{chat,speak}`
- `GET  /api/admin/vector-dbs`

Session 仍走 `cyberclone_session` HttpOnly Cookie；新增 CORS 配置允许 `http://127.0.0.1:5173` + 凭据。

生产模式下，FastAPI 用 `StaticFiles` 把 `frontend/dist` 挂到 `/`，并对所有未命中 API 的 GET 请求 fallback 返回 `frontend/dist/index.html`（SPA 路由）。

依赖新增（`pyproject.toml` 增 `[project.dependencies]`）：

- `fastapi>=0.110`
- `uvicorn[standard]>=0.27`
- `pydantic>=2.5`

### 前端

完全重写 `frontend/`：

```
frontend/
├── package.json
├── pnpm-lock.yaml 或 package-lock.json
├── vite.config.ts          # 含 /api 反代到 :8787
├── tsconfig.json
├── tsconfig.node.json
├── vitest.config.ts
├── index.html
├── src/
│   ├── main.ts             # createApp + pinia + router
│   ├── App.vue
│   ├── env.d.ts
│   ├── router/
│   │   └── index.ts        # /login /register /app /app/clones/:id /admin
│   ├── stores/
│   │   ├── auth.ts         # Pinia: 当前用户、login/logout/me
│   │   ├── clones.ts       # Pinia: 列表、当前 clone、CRUD
│   │   └── chat.ts         # Pinia: 对话消息 / 语音状态
│   ├── api/
│   │   ├── client.ts       # fetch 封装 + credentials: 'include'
│   │   ├── auth.ts
│   │   ├── clones.ts
│   │   ├── voice.ts
│   │   ├── chat.ts
│   │   └── admin.ts
│   ├── views/
│   │   ├── LoginView.vue
│   │   ├── RegisterView.vue
│   │   ├── AppView.vue          # 列表 + 创建表单 + 当前 clone
│   │   ├── CloneDetailView.vue  # 训练状态 + 聊天面板
│   │   └── AdminView.vue        # vector-db / voice-model 统计
│   ├── components/
│   │   ├── TopBar.vue
│   │   ├── CloneCreateForm.vue
│   │   ├── VoiceSampleUploader.vue
│   │   ├── VoiceRecorder.vue
│   │   ├── TrainingStatusPanel.vue
│   │   ├── ChatPanel.vue
│   │   ├── VoiceParameterPanel.vue
│   │   └── AdminResourceTable.vue
│   ├── composables/
│   │   ├── useFileToDataUrl.ts
│   │   └── useMicrophone.ts
│   ├── types.ts            # 与后端 schema 对应的 TS 类型
│   └── assets/
│       └── styles.css      # 从旧 assets/styles.css 平移
└── tests/
    ├── setup.ts
    └── *.spec.ts           # vitest，覆盖 8 个原 UI 测试场景
```

技术栈：

- Vue 3.4 + `<script setup>` + Composition API
- TypeScript 5
- Vite 5
- Pinia 2（状态管理）
- vue-router 4
- Vitest 1 + @vue/test-utils 2 + happy-dom（UI 测试）

### 测试

- **Python**：
  - 删除：`test_local_import_ui.py`、`test_auth_ui.py`、`test_voice_chat_ui.py`、`test_voice_parameter_ui.py`、`test_voice_model_control.py`（UI 层）、`test_frontend_routing.py`、`test_training_progress_ui.py`、`test_weflow_electron_ui.py`（8 个 UI 测试）。
  - 改造：`test_web_api.py` / `test_auth_web_api.py` 改用 `fastapi.testclient.TestClient`，断言 API 行为。
  - 保留：所有非 UI 的领域逻辑测试（chat_engine、storage、voice_models、vector_rag、rag、persona、auth、admin_stats、resource_layout、text_training、voxcpm_bridge、weflow 等）原样跑过。
- **前端**：vitest 覆盖 8 个原 UI 场景（登录注册、本地导入、训练进度、语音参数面板、语音模型控制、语音聊天 UI、前端路由、weflow electron UI）。

### 清理

- 删除旧 `web/` 目录（已与 frontend 不一致的旧拷贝）。
- 删除旧 `frontend/index.html` + `frontend/assets/*` vanilla JS。
- 旧 `chatService.ts` / `ExportPage.tsx` / `exportService.ts` 这三个根目录大文件未被引用，本轮不动；后续清理。

## 关键设计决定

### Cookie + CORS

前端 dev 在 :5173，后端 :8787。开发期通过 Vite 反代 `/api/*` 到 `http://127.0.0.1:8787`，前端永远只往同源 `/api/*` 发请求，自然带 Cookie，无 CORS 问题。

生产模式后端直接挂 `frontend/dist`，同源，问题不存在。

只在 `CYBERCLONE_DEV_CORS=1` 时打开 CORS（允许 `http://127.0.0.1:5173` + `credentials`），用于前端绕过 Vite 直连后端的边角场景。

### 文件上传

继续沿用现有 JSON + base64 data URL 协议（不改后端 schema）。理由：

- `voice_files[].data` 是 data URL，前端 `FileReader` + `MediaRecorder` 输出天然就是这种格式
- 不引入 multipart 改动让前端 store 状态机变复杂
- Pydantic 模型直接复用现有 `decode_upload_payload`

### Pydantic schemas

为每个 endpoint 写明确的请求/响应模型，但内部转换仍走现有的 `decode_upload_payload` 等函数 —— 减少冗余、保持现有验证逻辑不变。

### SPA 路由 fallback

FastAPI 添加 `@app.exception_handler(404)` 或全局 catch-all GET 路由：如果 URL 以 `/api/` 开头返回 JSON 404；否则返回 `frontend/dist/index.html`。

## 数据流（创建 clone 为例）

```
[CloneCreateForm.vue]
  ├─ 收集 targetName / chatText / voiceFiles / imageFiles ...
  ├─ 通过 useFileToDataUrl 把 File → data URL
  └─ api/clones.ts → POST /api/clones { ...JSON }
         │
         ▼
[FastAPI router clones.create]
  ├─ Depends(current_user)  → dict[str,str]
  ├─ Depends(get_store)     → CloneStore (per-user)
  ├─ Pydantic CloneCreateRequest 验证
  ├─ decode_upload_payload(...) → UploadPayload
  ├─ store.create_clone(...)    → CloneProfile  ← 复用现有逻辑
  └─ profile_to_api(profile)    → JSON
         │
         ▼
[Pinia clonesStore]
  ├─ 写入 list / current
  └─ router.push(`/app/clones/${clone.id}`)
```

## 风险与权衡

- **工作量大**：1500 行 JS → Vue 重写、16 条 API → FastAPI 重写、8 个 UI 测试 → vitest 重写。单轮对话内完成完整功能平移，需要写约 30+ 个新文件，可能在 token / 时间上吃紧。**应对**：先把"骨架 + 关键路径（auth / 列表 / 创建 clone / 文本聊天）"做扎实跑通，把其他视图（admin、语音录制、参数面板）按优先级补齐；如果某个视图未能在本轮完成，会在前端代码内显式标注，README 说明已完成范围。
- **session cookie 跨端口**：`SameSite=Lax` 在 :5173 → :8787 跨端口是允许的，但 Vite 反代天然消除了这个问题。
- **Pydantic 兼容**：要求 v2，与现有 Python 3.10+ 兼容。

## 不在本轮范围

- 把 `decode_upload_payload` 改成 Pydantic-only（保留现有验证函数包一层即可）
- 引入 alembic / 数据库迁移（项目目前用文件存储）
- 删除根目录 `chatService.ts` / `ExportPage.tsx` / `exportService.ts` 大文件（未引用，但不在本次清理范围）
- 替换 VoxCPM bridge 协议
- E2E 测试（playwright）

## 验收

1. `python -m cyberclone.api --port 8787` 启动后端；`pnpm --prefix frontend dev` 启动前端
2. 浏览器开 `http://127.0.0.1:5173`，能完成登录 / 注册 / 创建 clone / 文本聊天 / 上传语音样本 / 训练音色 / 语音聊天 / 管理员看资源统计
3. 生产模式：`pnpm --prefix frontend build` 后 `python -m cyberclone.api --port 8787` 单端口提供前后端
4. `pytest -q` 全绿（包含改造后的 `test_web_api.py` / `test_auth_web_api.py`）
5. `pnpm --prefix frontend test` 全绿
6. README 包含技术栈表、语音模型部署、本地开发与生产部署步骤
