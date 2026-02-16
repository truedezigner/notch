from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass

from fastapi import Header, HTTPException
from passlib.context import CryptContext

from .db import tx
from .settings import settings

# Use PBKDF2 (pure python) to avoid bcrypt backend/version issues inside slim containers.
pwd = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def now() -> int:
    return int(time.time())


def hash_password(p: str) -> str:
    return pwd.hash(p)


def verify_password(p: str, h: str) -> bool:
    return pwd.verify(p, h)


def issue_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    exp = now() + settings.SESSION_DAYS * 86400
    with tx() as con:
        con.execute(
            "INSERT INTO sessions(token,user_id,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?)",
            (token, user_id, now(), exp, now()),
        )
    return token


def get_user_by_session(token: str) -> dict:
    with tx() as con:
        row = con.execute(
            "SELECT u.id,u.handle,u.display_name FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND (s.expires_at IS NULL OR s.expires_at>?)",
            (token, now()),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid session")
        con.execute("UPDATE sessions SET last_seen_at=? WHERE token=?", (now(), token))
        return dict(row)


@dataclass
class Principal:
    kind: str  # user|service
    user: dict | None = None


def require_principal(authorization: str | None = Header(default=None)) -> Principal:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization")
    if not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Invalid Authorization")
    token = authorization.split(None, 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Invalid Authorization")

    # Service token for Tuesday integration
    if token == settings.SERVICE_TOKEN:
        return Principal(kind="service", user=None)

    # Otherwise treat as user session token
    user = get_user_by_session(token)
    return Principal(kind="user", user=user)
