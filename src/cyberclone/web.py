"""向后兼容的入口模块。

新代码请直接调用 ``cyberclone.api.create_app`` 或 ``python -m cyberclone.api``。
这里保留 ``python -m cyberclone.web --port 8787`` 入口和部分常量／纯函数
re-export，让旧的脚本和测试继续可用。
"""

from __future__ import annotations

import argparse

from .api import create_app
from .api import paths
from .api.conversions import (
    SpeechPayload,
    UploadedFile,
    UploadPayload,
    decode_speech_payload,
    decode_upload_payload,
    decode_voice_samples_payload,
    profile_to_api,
    speech_to_api,
)
from .voice import refresh_voice_training_status  # re-export，旧测试 monkeypatch 用

PROJECT_ROOT = paths.PROJECT_ROOT
FRONTEND_ROOT = paths.PROJECT_ROOT / "frontend"
WEB_ROOT = FRONTEND_ROOT
DATA_ROOT = paths.DATA_ROOT
SESSION_COOKIE_NAME = paths.SESSION_COOKIE_NAME

__all__ = [
    "PROJECT_ROOT",
    "FRONTEND_ROOT",
    "WEB_ROOT",
    "DATA_ROOT",
    "SESSION_COOKIE_NAME",
    "SpeechPayload",
    "UploadedFile",
    "UploadPayload",
    "create_app",
    "decode_speech_payload",
    "decode_upload_payload",
    "decode_voice_samples_payload",
    "profile_to_api",
    "speech_to_api",
    "refresh_voice_training_status",
    "run",
    "main",
]


def run(host: str = "127.0.0.1", port: int = 8787) -> None:
    """启动 FastAPI + uvicorn，等价于 ``python -m cyberclone.api``。"""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - 仅在依赖缺失时触发
        raise SystemExit(
            "缺少 uvicorn 依赖。请先执行 `pip install fastapi 'uvicorn[standard]' pydantic`。"
        ) from exc

    uvicorn.run(create_app(), host=host, port=port, log_level="info")


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Cyber Clone Web 服务（FastAPI + uvicorn）。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    run(args.host, args.port)


if __name__ == "__main__":  # pragma: no cover - CLI 入口
    main()
