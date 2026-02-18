from __future__ import annotations

import json
import time
import uuid
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

import asyncio

from .auth import Principal, hash_password, issue_session, require_principal, verify_password
from .db import tx
from .settings import settings
from . import todos as todos_api
from . import lists as lists_api
from . import notes as notes_api
from .scheduler import run_once


def _html_escape(s: str) -> str:
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def now() -> int:
    return int(time.time())


def is_admin_user(user_id: str) -> bool:
    # Admin = the first user ever created (bootstrap user). Simple and works for LAN MVP.
    with tx() as con:
        row = con.execute("SELECT id FROM users ORDER BY created_at ASC LIMIT 1").fetchone()
        if not row:
            return False
        return row["id"] == user_id


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
    return {
        "ok": True,
        "token": token,
        "user": {
            "id": row["id"],
            "handle": row["handle"],
            "display_name": row["display_name"],
            "is_admin": is_admin_user(row["id"]),
        },
    }


@app.get("/api/me")
async def me(p: Principal = Depends(require_principal)):
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="Not a user session")
    u = dict(p.user or {})
    u["is_admin"] = is_admin_user(u.get("id") or "")
    return {"ok": True, "user": u}


@app.get("/api/users")
async def list_users(p: Principal = Depends(require_principal)):
    # allow service to map handles; allow users too.
    with tx() as con:
        rows = con.execute("SELECT id,handle,display_name,created_at FROM users ORDER BY handle").fetchall()
    first_id = None
    if rows:
        first_id = sorted([dict(r) for r in rows], key=lambda x: int(x.get("created_at") or 0))[0]["id"]
    users = []
    for r in rows:
        d = dict(r)
        d.pop("created_at", None)
        d["is_admin"] = (d.get("id") == first_id)
        users.append(d)
    return {"ok": True, "users": users}


# --- Todo lists ---

@app.get("/api/lists")
async def list_lists(p: Principal = Depends(require_principal)):
    lists = lists_api.list_lists(p=p)
    return {"ok": True, "lists": lists}


@app.post("/api/lists")
async def create_list(payload: dict, p: Principal = Depends(require_principal)):
    lst = lists_api.create_list(p=p, payload=payload)
    return {"ok": True, "list": lst}


@app.delete("/api/lists/{list_id}")
async def delete_list(list_id: str, p: Principal = Depends(require_principal)):
    return lists_api.delete_list(p=p, list_id=list_id)


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


@app.patch("/api/note-groups/{group_id}")
async def patch_note_group(group_id: str, payload: dict, p: Principal = Depends(require_principal)):
    group = notes_api.patch_group(p=p, group_id=group_id, payload=payload)
    return {"ok": True, "group": group}


@app.get("/api/notes")
async def list_notes(
    query: str | None = None,
    group_id: str | None = None,
    include_deleted: int = 0,
    deleted_only: int = 0,
    limit: int = 200,
    p: Principal = Depends(require_principal),
):
    notes = notes_api.list_notes(
        p=p,
        query=query,
        group_id=group_id,
        include_deleted=bool(include_deleted),
        deleted_only=bool(deleted_only),
        limit=limit,
    )
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


@app.post("/api/notes/{note_id}/restore")
async def restore_note(note_id: str, p: Principal = Depends(require_principal)):
    note = notes_api.restore_note(p=p, note_id=note_id)
    return {"ok": True, "note": note}


@app.post("/api/notes/{note_id}/share")
async def create_note_share(note_id: str, payload: dict, p: Principal = Depends(require_principal)):
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    # You must be able to see the note to share it.
    note = notes_api.get_note(p=p, note_id=note_id)

    can_edit = payload.get("can_edit")
    can_edit_i = 1 if (can_edit is None or bool(can_edit)) else 0

    expires_in = payload.get("expires_in_seconds")
    expires_at = None
    if expires_in is not None and expires_in != "":
        try:
            expires_in_i = int(expires_in)
            if expires_in_i > 0:
                expires_at = now() + expires_in_i
        except Exception:
            raise HTTPException(status_code=400, detail="expires_in_seconds must be int")

    token = secrets.token_urlsafe(24)
    with tx() as con:
        con.execute(
            "INSERT INTO note_shares(token,note_id,created_by,can_edit,expires_at,created_at) VALUES(?,?,?,?,?,?)",
            (token, note_id, p.user["id"], can_edit_i, expires_at, now()),
        )

    # Link points to a public, no-auth page.
    # Use relative URL; frontend will prefix with origin.
    return {"ok": True, "token": token, "url": f"/share/n/{token}", "can_edit": bool(can_edit_i), "expires_at": expires_at, "note_id": note.get("id")}


@app.get("/api/todos")
async def list_todos(
    query: str | None = None,
    include_done: int = 0,
    list_id: str | None = None,
    include_deleted: int = 0,
    deleted_only: int = 0,
    limit: int = 200,
    p: Principal = Depends(require_principal),
):
    todos = todos_api.list_todos(
        p=p,
        query=query,
        include_done=bool(include_done),
        list_id=list_id,
        include_deleted=bool(include_deleted),
        deleted_only=bool(deleted_only),
        limit=limit,
    )
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


@app.delete("/api/todos/{todo_id}/purge")
async def purge_todo(todo_id: str, p: Principal = Depends(require_principal)):
    return todos_api.purge_todo(p=p, todo_id=todo_id)


@app.post("/api/todos/{todo_id}/restore")
async def restore_todo(todo_id: str, p: Principal = Depends(require_principal)):
    todo = todos_api.restore_todo(p=p, todo_id=todo_id)
    return {"ok": True, "todo": todo}


@app.post("/api/admin/users")
async def admin_create_user(payload: dict, p: Principal = Depends(require_principal)):
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    if not is_admin_user(p.user["id"]):
        raise HTTPException(status_code=403, detail="Admin required")

    handle = (payload.get("handle") or payload.get("username") or "").strip().lower()
    display_name = (payload.get("display_name") or handle).strip() or handle
    password = (payload.get("password") or "").strip()
    if not handle or not password:
        raise HTTPException(status_code=400, detail="Missing handle/password")

    uid = str(uuid.uuid4())
    t = now()
    with tx() as con:
        exists = con.execute("SELECT 1 FROM users WHERE handle=?", (handle,)).fetchone()
        if exists:
            raise HTTPException(status_code=409, detail="Handle already exists")
        con.execute(
            "INSERT INTO users(id,handle,display_name,password_hash,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (uid, handle, display_name, hash_password(password), t, t),
        )
        row = con.execute("SELECT id,handle,display_name FROM users WHERE id=?", (uid,)).fetchone()

    return {"ok": True, "user": dict(row)}


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


@app.get("/share/n/{token}")
async def public_note_share_page(token: str):
    # Minimal public editor/viewer (no auth). Fetches note via public API.
    # Keeps it simple for LAN MVP.
    token_json = json.dumps(token)
    html = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Notch Share</title>
  <style>
    body { margin:0; font-family: system-ui, -apple-system, sans-serif; background:#0b0f14; color:#e6edf3; }
    .wrap { max-width: 900px; margin: 0 auto; padding: 16px; }
    .card { border: 1px solid #243041; border-radius: 12px; background:#111826; padding: 12px; }
    input, textarea { width: 100%; box-sizing: border-box; padding: 10px; border-radius: 10px; border: 1px solid #243041; background:#111826; color:#e6edf3; font: inherit; }
    textarea { min-height: 320px; resize: vertical; }
    .row { display:flex; gap:10px; align-items:center; justify-content:space-between; flex-wrap: wrap; }
    .muted { color:#9aa4af; font-size: 12px; }
    .pill { border: 1px solid #243041; border-radius: 999px; padding: 2px 8px; font-size: 12px; color:#9aa4af; }
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"row\" style=\"margin-bottom:10px;\">
      <h2 style=\"margin:0;\">Notch</h2>
      <span class=\"pill\">Shared note</span>
    </div>
    <div class=\"card\">
      <div class=\"row\">
        <div class=\"muted\" id=\"status\">Loading…</div>
      </div>
      <div style=\"margin-top:10px;\">
        <input id=\"title\" placeholder=\"Title\" />
      </div>
      <div style=\"margin-top:10px;\">
        <textarea id=\"body\" placeholder=\"Markdown…\"></textarea>
      </div>
      <div class=\"muted\" style=\"margin-top:10px;\">Autosaves when you stop typing.</div>
    </div>
  </div>

<script>
const token = __TOKEN__;
let version = null;
let canEdit = true;
let timer = null;

const statusEl = document.getElementById('status');
const titleEl = document.getElementById('title');
const bodyEl = document.getElementById('body');

function setStatus(t){ statusEl.textContent = t; }

async function load(){
  setStatus('Loading…');
  const res = await fetch(`/api/public/notes/${encodeURIComponent(token)}`);
  const j = await res.json();
  if (!res.ok) throw new Error(j?.detail || 'Failed');
  titleEl.value = j.note.title || '';
  bodyEl.value = j.note.body_md || '';
  version = j.note.version;
  canEdit = !!j.can_edit;
  titleEl.disabled = !canEdit;
  bodyEl.disabled = !canEdit;
  setStatus(canEdit ? 'Editable link' : 'View-only link');
}

async function save(){
  if (!canEdit) return;
  setStatus('Saving…');
  const res = await fetch(`/api/public/notes/${encodeURIComponent(token)}` , {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: titleEl.value, body_md: bodyEl.value, if_version: version })
  });
  const j = await res.json();
  if (!res.ok) {
    setStatus(j?.detail || 'Save failed');
    // best-effort reload
    try { await load(); } catch {}
    return;
  }
  version = j.note.version;
  setStatus('Saved');
}

function dirty(){
  if (!canEdit) return;
  setStatus('Unsaved');
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => { timer=null; save(); }, 650);
}

titleEl.addEventListener('input', dirty);
bodyEl.addEventListener('input', dirty);

load().catch(e => { setStatus(String(e?.message || e)); });
</script>
</body>
</html>""".replace("__TOKEN__", token_json)

    return HTMLResponse(content=html)


@app.get("/api/public/notes/{token}")
async def public_get_note(token: str):
    with tx() as con:
        row = con.execute("SELECT * FROM note_shares WHERE token=?", (token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        share = dict(row)
        if share.get("expires_at") is not None and int(share.get("expires_at") or 0) <= now():
            raise HTTPException(status_code=410, detail="Link expired")
        nrow = con.execute("SELECT id,title,body_md,version,updated_at,deleted_at FROM notes WHERE id=?", (share["note_id"],)).fetchone()
        if not nrow:
            raise HTTPException(status_code=404, detail="Not found")
        note = dict(nrow)
        if note.get("deleted_at") is not None:
            raise HTTPException(status_code=404, detail="Not found")
        note.pop("deleted_at", None)

    return {"ok": True, "note": note, "can_edit": bool(int(share.get("can_edit") or 0)), "expires_at": share.get("expires_at")}


@app.patch("/api/public/notes/{token}")
async def public_patch_note(token: str, payload: dict):
    with tx() as con:
        row = con.execute("SELECT * FROM note_shares WHERE token=?", (token,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        share = dict(row)
        if share.get("expires_at") is not None and int(share.get("expires_at") or 0) <= now():
            raise HTTPException(status_code=410, detail="Link expired")
        if not bool(int(share.get("can_edit") or 0)):
            raise HTTPException(status_code=403, detail="Read-only link")

    # Reuse the normal patch logic, but bypass auth with a synthetic principal.
    # Principal.user only needs id for version check logic.
    p = Principal(kind="user", user={"id": share["created_by"], "handle": "public", "display_name": "Public"})
    note = notes_api.patch_note(p=p, note_id=str(share["note_id"]), payload=payload)
    return {"ok": True, "note": note}


@app.get("/app/{path:path}")
async def spa(path: str):
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    raise HTTPException(status_code=503, detail="Frontend not built")
