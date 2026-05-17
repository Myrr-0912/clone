from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

USER_STORE_PATH = Path("data/auth/users.json")
SESSION_STORE_PATH = Path("data/auth/sessions.json")
DEFAULT_ADMIN_USERNAME = "admin"
DEFAULT_ADMIN_PASSWORD = "admin"

_ALLOWED_ROLES = {"user", "admin"}
_HASH_NAME = "sha256"
_PBKDF2_ITERATIONS = 260_000
_SALT_BYTES = 16

_USER_LOCK = threading.RLock()
_SESSION_LOCK = threading.RLock()


def register(username: str, password: str, role: str = "user") -> dict[str, str]:
    normalized_username = _normalize_username(username)
    _validate_password(password)
    if role not in _ALLOWED_ROLES:
        raise ValueError("Role must be user or admin")

    with _USER_LOCK:
        store = _load_user_store()
        users = store["users"]
        if any(user["username"] == normalized_username for user in users):
            raise ValueError("Username already exists")

        user = {
            "id": secrets.token_hex(16),
            "username": normalized_username,
            "role": role,
            "hash_name": _HASH_NAME,
            "iterations": _PBKDF2_ITERATIONS,
            "created_at": _now_iso(),
        }
        _set_password_fields(user, password)
        users.append(user)
        _write_json(USER_STORE_PATH, store)
        return _public_user(user)


def ensure_default_admin(
    username: str = DEFAULT_ADMIN_USERNAME,
    password: str = DEFAULT_ADMIN_PASSWORD,
) -> dict[str, str]:
    """Ensure the local MVP has a known administrator account."""
    normalized_username = _normalize_username(username)
    _validate_password(password)

    with _USER_LOCK:
        store = _load_user_store()
        users = store["users"]
        user = next((item for item in users if item["username"] == normalized_username), None)
        if user is None:
            user = {
                "id": secrets.token_hex(16),
                "username": normalized_username,
                "role": "admin",
                "hash_name": _HASH_NAME,
                "iterations": _PBKDF2_ITERATIONS,
                "created_at": _now_iso(),
            }
            users.append(user)
        else:
            user["role"] = "admin"

        _set_password_fields(user, password)
        _write_json(USER_STORE_PATH, store)
        return _public_user(user)


def authenticate(username: str, password: str) -> dict[str, str] | None:
    try:
        normalized_username = _normalize_username(username)
    except ValueError:
        return None
    if not isinstance(password, str) or not password:
        return None

    with _USER_LOCK:
        for user in _load_user_store()["users"]:
            if user["username"] != normalized_username:
                continue
            salt = bytes.fromhex(user["salt"])
            iterations = int(user.get("iterations", _PBKDF2_ITERATIONS))
            expected_hash = bytes.fromhex(user["password_hash"])
            actual_hash = _hash_password(password, salt, iterations)
            if hmac.compare_digest(actual_hash, expected_hash):
                return _public_user(user)
            return None
    return None


def create_session(user_id: str) -> str:
    if not isinstance(user_id, str) or not user_id.strip():
        raise ValueError("User id is required")
    if _find_user_by_id(user_id) is None:
        raise ValueError("User not found")

    with _SESSION_LOCK:
        store = _load_session_store()
        existing_tokens = {session["token"] for session in store["sessions"]}
        token = secrets.token_urlsafe(32)
        while token in existing_tokens:
            token = secrets.token_urlsafe(32)
        store["sessions"].append(
            {
                "token": token,
                "user_id": user_id,
                "created_at": _now_iso(),
            }
        )
        _write_json(SESSION_STORE_PATH, store)
        return token


def get_session(token: str) -> dict[str, Any] | None:
    if not isinstance(token, str) or not token:
        return None

    with _SESSION_LOCK:
        sessions = _load_session_store()["sessions"]
        session = next((item for item in sessions if item["token"] == token), None)
    if session is None:
        return None

    user = _find_user_by_id(session["user_id"])
    if user is None:
        return None
    return {**session, "user": _public_user(user)}


def delete_session(token: str) -> bool:
    if not isinstance(token, str) or not token:
        return False

    with _SESSION_LOCK:
        store = _load_session_store()
        original_count = len(store["sessions"])
        store["sessions"] = [session for session in store["sessions"] if session["token"] != token]
        if len(store["sessions"]) == original_count:
            return False
        _write_json(SESSION_STORE_PATH, store)
        return True


def _normalize_username(username: str) -> str:
    if not isinstance(username, str):
        raise ValueError("Username is required")
    normalized = username.strip().casefold()
    if not normalized:
        raise ValueError("Username is required")
    return normalized


def _validate_password(password: str) -> None:
    if not isinstance(password, str) or not password:
        raise ValueError("Password is required")


def _hash_password(password: str, salt: bytes, iterations: int) -> bytes:
    return hashlib.pbkdf2_hmac(_HASH_NAME, password.encode("utf-8"), salt, iterations)


def _set_password_fields(user: dict[str, Any], password: str) -> None:
    salt = secrets.token_bytes(_SALT_BYTES)
    user["password_hash"] = _hash_password(password, salt, _PBKDF2_ITERATIONS).hex()
    user["salt"] = salt.hex()
    user["hash_name"] = _HASH_NAME
    user["iterations"] = _PBKDF2_ITERATIONS


def _public_user(user: dict[str, Any]) -> dict[str, str]:
    return {
        "id": str(user["id"]),
        "username": str(user["username"]),
        "role": str(user["role"]),
    }


def _find_user_by_id(user_id: str) -> dict[str, Any] | None:
    with _USER_LOCK:
        return next((user for user in _load_user_store()["users"] if user["id"] == user_id), None)


def _load_user_store() -> dict[str, list[dict[str, Any]]]:
    store = _read_json(USER_STORE_PATH, {"users": []})
    users = store.get("users")
    if not isinstance(users, list):
        raise ValueError("User store must contain a users list")
    return {"users": users}


def _load_session_store() -> dict[str, list[dict[str, Any]]]:
    store = _read_json(SESSION_STORE_PATH, {"sessions": []})
    sessions = store.get("sessions")
    if not isinstance(sessions, list):
        raise ValueError("Session store must contain a sessions list")
    return {"sessions": sessions}


def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        return default.copy()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON store: {path}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON store must contain an object: {path}")
    return data


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f"{path.name}.tmp")
    temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(path)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
