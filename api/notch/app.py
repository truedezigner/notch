from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import asyncio

from .auth import Principal, hash_password, issue_session, require_principal, verify_password
from .db import tx
from .settings import settings
from . import todos as todos_api
from . import lists as lists_api
from . import notes as notes_api
from .scheduler import run_once


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

    # Background scheduler loop (reminders -> ntfy)
    async def _loop():
        # tiny delay so app finishes booting
        await asyncio.sleep(0.25)
        while True:
            try:
                await run_once()
            except Exception:
                # best-effort; logs will show details via uvicorn
                pass
            await asyncio.sleep(max(0.25, float(settings.SCHEDULER_POLL_SECONDS)))

    if settings.SCHEDULER_ENABLED:
        asyncio.create_task(_loop())


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


# --- Todo lists ---

@app.get("/api/lists")
async def list_lists(p: Principal = Depends(require_principal)):
    lists = lists_api.list_lists(p=p)
    return {"ok": True, "lists": lists}


@app.post("/api/lists")
async def create_list(payload: dict, p: Principal = Depends(require_principal)):
    lst = lists_api.create_list(p=p, payload=payload)
    return {"ok": True, "list": lst}


# --- Todos ---

@app.post("/api/todos")
async def create_todo(payload: dict, p: Principal = Depends(require_principal)):
    todo = todos_api.create_todo(p=p, payload=payload)
    return {"ok": True, "todo": todo}


# --- Note groups / Notes ---

@app.get("/api/note-groups")
async def list_note_groups(p: Principal = Depends(require_principal)):
    groups = notes_api.list_groups(p=p)
    return {"ok": True, "groups": groups}


@app.post("/api/note-groups")
async def create_note_group(payload: dict, p: Principal = Depends(require_principal)):
    group = notes_api.create_group(p=p, payload=payload)
    return {"ok": True, "group": group}


@app.get("/api/notes")
async def list_notes(
    query: str | None = None,
    group_id: str | None = None,
    limit: int = 200,
    p: Principal = Depends(require_principal),
):
    notes = notes_api.list_notes(p=p, query=query, group_id=group_id, limit=limit)
    return {"ok": True, "notes": notes}


@app.post("/api/notes")
async def create_note(payload: dict, p: Principal = Depends(require_principal)):
    note = notes_api.create_note(p=p, payload=payload)
    return {"ok": True, "note": note}


@app.get("/api/notes/{note_id}")
async def get_note(note_id: str, p: Principal = Depends(require_principal)):
    note = notes_api.get_note(p=p, note_id=note_id)
    return {"ok": True, "note": note}


@app.patch("/api/notes/{note_id}")
async def patch_note(note_id: str, payload: dict, p: Principal = Depends(require_principal)):
    note = notes_api.patch_note(p=p, note_id=note_id, payload=payload)
    return {"ok": True, "note": note}


@app.delete("/api/notes/{note_id}")
async def delete_note(note_id: str, p: Principal = Depends(require_principal)):
    return notes_api.delete_note(p=p, note_id=note_id)


@app.get("/api/todos")
async def list_todos(
    query: str | None = None,
    include_done: int = 0,
    list_id: str | None = None,
    limit: int = 200,
    p: Principal = Depends(require_principal),
):
    todos = todos_api.list_todos(p=p, query=query, include_done=bool(include_done), list_id=list_id, limit=limit)
    return {"ok": True, "todos": todos}


@app.get("/api/todos/{todo_id}")
async def get_todo(todo_id: str, p: Principal = Depends(require_principal)):
    todo = todos_api.get_todo(p=p, todo_id=todo_id)
    return {"ok": True, "todo": todo}


@app.patch("/api/todos/{todo_id}")
async def patch_todo(todo_id: str, payload: dict, p: Principal = Depends(require_principal)):
    todo = todos_api.patch_todo(p=p, todo_id=todo_id, payload=payload)
    return {"ok": True, "todo": todo}


@app.delete("/api/todos/{todo_id}")
async def delete_todo(todo_id: str, p: Principal = Depends(require_principal)):
    return todos_api.delete_todo(p=p, todo_id=todo_id)


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
