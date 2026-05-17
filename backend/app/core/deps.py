"""FastAPI 依赖注入：当前用户、管理员、CloneStore。"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status

from app.core import paths
from app.core import security as auth
from app.services.storage import CloneStore
from app.services.text_training import make_text_profile_builder


def current_session(
    session_token: Annotated[str | None, Cookie(alias=paths.SESSION_COOKIE_NAME)] = None,
) -> dict[str, object] | None:
    if not session_token:
        return None
    return auth.get_session(session_token)


def current_user(
    session: Annotated[dict[str, object] | None, Depends(current_session)],
) -> dict[str, str]:
    if session is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return session["user"]  # type: ignore[return-value]


def require_admin(
    user: Annotated[dict[str, str], Depends(current_user)],
) -> dict[str, str]:
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user


def get_store(
    user: Annotated[dict[str, str], Depends(current_user)],
) -> CloneStore:
    return CloneStore(
        paths.data_root(),
        text_profile_builder=make_text_profile_builder(paths.env_path()),
        user_id=user["id"],
    )


CurrentSession = Annotated[dict[str, object] | None, Depends(current_session)]
CurrentUser = Annotated[dict[str, str], Depends(current_user)]
AdminUser = Annotated[dict[str, str], Depends(require_admin)]
StoreDep = Annotated[CloneStore, Depends(get_store)]
