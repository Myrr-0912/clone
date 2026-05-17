"""Session cookie 设置工具，保持与旧 web.py 一致的格式。"""

from __future__ import annotations

from fastapi import Response

from . import paths


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=paths.SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.set_cookie(
        key=paths.SESSION_COOKIE_NAME,
        value="",
        max_age=0,
        httponly=True,
        samesite="lax",
        path="/",
    )
