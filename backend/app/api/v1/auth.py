"""认证相关路由：/api/v1/auth/{me,register,login,logout}。"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.core import security as auth
from app.core.cookies import clear_session_cookie, set_session_cookie
from app.core.deps import CurrentSession

router = APIRouter(prefix="/auth", tags=["auth"])


class CredentialsPayload(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


@router.get("/me")
def me(session: CurrentSession) -> dict[str, Any]:
    return {"user": session["user"] if session else None}


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: CredentialsPayload, response: Response) -> dict[str, Any]:
    try:
        user = auth.register(payload.username, payload.password)
        token = auth.create_session(user["id"])
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    set_session_cookie(response, token)
    return {"user": user}


@router.post("/login")
def login(payload: CredentialsPayload, response: Response) -> dict[str, Any]:
    try:
        user = auth.authenticate(payload.username, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid username or password"
        )

    token = auth.create_session(user["id"])
    set_session_cookie(response, token)
    return {"user": user}


@router.post("/logout")
def logout(session: CurrentSession, response: Response) -> dict[str, Any]:
    if session is not None:
        token = session.get("token")
        if isinstance(token, str) and token:
            auth.delete_session(token)
    clear_session_cookie(response)
    return {"ok": True}
