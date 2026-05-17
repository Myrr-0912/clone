"""``python -m app --port 8787`` 启动入口。"""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(description="启动 Cyber Clone Lab FastAPI 服务。")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument(
        "--reload",
        action="store_true",
        help="开发期自动 reload，等价于 uvicorn --reload",
    )
    args = parser.parse_args()

    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - 仅在依赖缺失时触发
        raise SystemExit(
            "缺少 uvicorn 依赖。请先执行 `pip install fastapi 'uvicorn[standard]' "
            "pydantic pydantic-settings`。"
        ) from exc

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info",
    )


if __name__ == "__main__":
    main()
