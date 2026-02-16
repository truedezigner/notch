from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import Principal, hash_password, issue_session, require_principal, verify_password
from .db import connect, tx
from .settings import settings


def now() -> int:
    return int(time.time())


def init_db() -> None:
    from . import schema  # noqa


app = FastAPI(title="notch", version="0.1.0")


@app.on_event("startup")
async def _startup():
    # Initialize schema
    from .schema import apply_schema

    apply_schema()


@app.get("/health")
async def health():
    return {"ok": True, "service": "notch"}


@app.post("/api/auth/login")
async def login(payload: dict):
    handle = (payload.get("handle") or payload.get("username") or "").strip().lower()
    password = (payload.get("password") or "").strip()
    if not handle or not password:
        raise HTTPException(status_code=400, detail="Missing handle/password")

    with tx() as con:
        row = con.execute("SELECT id,handle,display_name,password_hash FROM users WHERE handle=?", (handle,)).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid login")
        if not verify_password(password, row["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid login")

    token = issue_session(row["id"])
    return {"ok": True, "token": token, "user": {"id": row["id"], "handle": row["handle"], "display_name": row["display_name"]}}


@app.get("/api/me")
async def me(p: Principal = Depends(require_principal)):
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="Not a user session")
    return {"ok": True, "user": p.user}


@app.get("/api/users")
async def list_users(p: Principal = Depends(require_principal)):
    # allow service to map handles; allow users too.
    with tx() as con:
        rows = con.execute("SELECT id,handle,display_name FROM users ORDER BY handle").fetchall()
    return {"ok": True, "users": [dict(r) for r in rows]}


@app.post("/api/admin/bootstrap")
async def bootstrap_admin(payload: dict):
    """One-time bootstrap: create first user if none exist.

    This avoids having to ship a separate migration/admin UI on day 1.
    """
    handle = (payload.get("handle") or "").strip().lower()
    display_name = (payload.get("display_name") or handle).strip() or handle
    password = (payload.get("password") or "").strip()
    if not handle or not password:
        raise HTTPException(status_code=400, detail="Missing handle/password")

    with tx() as con:
        n = con.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]
        if n and int(n) > 0:
            raise HTTPException(status_code=409, detail="Already bootstrapped")
        uid = str(uuid.uuid4())
        t = now()
        con.execute(
            "INSERT INTO users(id,handle,display_name,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (uid, handle, display_name, hash_password(password), t, t),
        )

    return {"ok": True, "note": "Bootstrapped"}


# --- SPA/static ---

# In production we serve built assets from api/static.
static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")


@app.get("/app/{path:path}")
async def spa(path: str):
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=503, detail="Frontend not built")
