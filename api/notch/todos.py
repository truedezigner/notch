from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import HTTPException

from .auth import Principal
from .db import tx
from .lists import ensure_default_list


def now() -> int:
    return int(time.time())


def _loads_list(s: str | None) -> list[str]:
    if not s:
        return []
    try:
        v = json.loads(s)
        if isinstance(v, list):
            return [str(x) for x in v]
    except Exception:
        pass
    return []


def _dumps_list(v: list[str] | None) -> str:
    return json.dumps(v or [], ensure_ascii=False)


def create_todo(*, p: Principal, payload: dict) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    title = (payload.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Missing title")

    # Todos are title-only (no description field)
    notes = None
    due_at = payload.get("due_at")
    remind_at = payload.get("remind_at")
    list_id = payload.get("list_id")
    assigned_to = payload.get("assigned_to")
    shared_with = payload.get("shared_with")

    # Normalize ints
    def to_int(x):
        if x is None or x == "":
            return None
        try:
            return int(x)
        except Exception:
            raise HTTPException(status_code=400, detail="due_at/remind_at must be unix seconds")

    due_at_i = to_int(due_at)
    remind_at_i = to_int(remind_at)

    if assigned_to is not None and assigned_to != "":
        assigned_to = str(assigned_to)
    else:
        assigned_to = None

    if isinstance(shared_with, list):
        shared_with_s = _dumps_list([str(x) for x in shared_with])
    elif shared_with is None:
        shared_with_s = _dumps_list([])
    else:
        raise HTTPException(status_code=400, detail="shared_with must be a list")

    # Default list = Inbox
    if not list_id:
        inbox = ensure_default_list(p.user["id"])
        list_id = inbox["id"]

    tid = str(uuid.uuid4())
    t = now()
    with tx() as con:
        con.execute(
            """
            INSERT INTO todos(id,list_id,title,notes,done,due_at,remind_at,remind_sent_at,assigned_to,shared_with,created_by,created_at,updated_at,version)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (tid, str(list_id), title, notes, 0, due_at_i, remind_at_i, None, assigned_to, shared_with_s, p.user["id"], t, t, 1),
        )
        row = con.execute("SELECT * FROM todos WHERE id=?", (tid,)).fetchone()
    return _row_to_todo(dict(row))


def list_todos(
    *,
    p: Principal,
    query: str | None,
    include_done: bool = False,
    list_id: str | None = None,
    include_deleted: bool = False,
    deleted_only: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    q = (query or "").strip().lower()
    params: list[Any] = []
    where = ["(created_by=? OR assigned_to=? OR instr(shared_with, ?) > 0)"]
    params.extend([p.user["id"], p.user["id"], p.user["id"]])

    if not include_done:
        where.append("done=0")

    if list_id:
        where.append("list_id=?")
        params.append(str(list_id))

    if not include_deleted:
        where.append("deleted_at IS NULL")
    if deleted_only:
        where.append("deleted_at IS NOT NULL")

    if q:
        where.append("(lower(title) LIKE ?)")
        params.extend([f"%{q}%"])

    # Sort: undone first, then due date, then remind time.
    sql = (
        "SELECT * FROM todos WHERE "
        + " AND ".join(where)
        + " ORDER BY done ASC, COALESCE(due_at, 2147483647) ASC, COALESCE(remind_at, 2147483647) ASC, updated_at DESC LIMIT ?"
    )
    params.append(int(limit))

    with tx() as con:
        rows = con.execute(sql, params).fetchall()
    return [_row_to_todo(dict(r)) for r in rows]


def get_todo(*, p: Principal, todo_id: str) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    with tx() as con:
        row = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        todo = dict(row)
    if todo.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Not found")
    # Permissions: same check as list
    if not _can_see(p.user["id"], todo):
        raise HTTPException(status_code=404, detail="Not found")
    return _row_to_todo(todo)


def delete_todo(*, p: Principal, todo_id: str) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    with tx() as con:
        row = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)
        if not _can_see(p.user["id"], cur):
            raise HTTPException(status_code=404, detail="Not found")
        # Only creator can delete (safer than allowing shared users to delete your data).
        if cur.get("created_by") != p.user["id"]:
            raise HTTPException(status_code=403, detail="Only creator can delete")

        t = now()
        con.execute(
            "UPDATE todos SET deleted_at=?, updated_at=?, version=version+1 WHERE id=?",
            (t, t, todo_id),
        )

    return {"ok": True, "deleted": True, "id": todo_id}


def purge_todo(*, p: Principal, todo_id: str) -> dict[str, Any]:
    """Permanently delete a todo.

    By default this is only used from the Trash view.
    Permissions: any user who can see the todo (creator/assignee/shared) may purge.
    """
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    with tx() as con:
        row = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)
        if not _can_see(p.user["id"], cur):
            raise HTTPException(status_code=404, detail="Not found")

        # Only allow purge from Trash (safety)
        if cur.get("deleted_at") is None:
            raise HTTPException(status_code=409, detail="Todo is not in Trash")

        con.execute("DELETE FROM todos WHERE id=?", (todo_id,))

    return {"ok": True, "purged": True, "id": todo_id}


def restore_todo(*, p: Principal, todo_id: str) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    with tx() as con:
        row = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)
        if cur.get("created_by") != p.user["id"]:
            raise HTTPException(status_code=403, detail="Only creator can restore")

        t = now()
        con.execute(
            "UPDATE todos SET deleted_at=NULL, updated_at=?, version=version+1 WHERE id=?",
            (t, todo_id),
        )
        row2 = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()

    return _row_to_todo(dict(row2))


def patch_todo(*, p: Principal, todo_id: str, payload: dict) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    if_version = payload.get("if_version")
    if if_version is not None:
        try:
            if_version = int(if_version)
        except Exception:
            raise HTTPException(status_code=400, detail="if_version must be int")

    fields = {}
    # Title only. Ignore notes/description edits.
    for k in ("title",):
        if k in payload:
            v = payload.get(k)
            if v is None:
                fields[k] = None
            else:
                fields[k] = str(v).strip()

    for k in ("done",):
        if k in payload:
            v = payload.get(k)
            fields[k] = 1 if bool(v) else 0

    def to_int_nullable(x):
        if x is None or x == "":
            return None
        return int(x)

    for k in ("due_at", "remind_at"):
        if k in payload:
            try:
                fields[k] = to_int_nullable(payload.get(k))
            except Exception:
                raise HTTPException(status_code=400, detail=f"{k} must be unix seconds")

    if "assigned_to" in payload:
        v = payload.get("assigned_to")
        fields["assigned_to"] = None if (v is None or v == "") else str(v)

    if "shared_with" in payload:
        v = payload.get("shared_with")
        if not isinstance(v, list):
            raise HTTPException(status_code=400, detail="shared_with must be list")
        fields["shared_with"] = _dumps_list([str(x) for x in v])

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    with tx() as con:
        row = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)
        if cur.get("deleted_at") is not None:
            raise HTTPException(status_code=409, detail="Todo is in trash")
        if not _can_see(p.user["id"], cur):
            raise HTTPException(status_code=404, detail="Not found")

        if if_version is not None and int(cur.get("version") or 0) != if_version:
            raise HTTPException(status_code=409, detail="Version conflict")

        # If remind_at is changed, clear remind_sent_at so it can notify again.
        if "remind_at" in fields:
            old = cur.get("remind_at")
            new = fields.get("remind_at")
            try:
                old_i = None if old is None else int(old)
            except Exception:
                old_i = None
            try:
                new_i = None if new is None else int(new)
            except Exception:
                new_i = None
            if old_i != new_i:
                fields["remind_sent_at"] = None

        sets = []
        params: list[Any] = []
        for k, v in fields.items():
            sets.append(f"{k}=?")
            params.append(v)
        t = now()
        sets.append("updated_at=?")
        params.append(t)
        sets.append("version=version+1")

        params.append(todo_id)

        con.execute(f"UPDATE todos SET {', '.join(sets)} WHERE id=?", params)
        row2 = con.execute("SELECT * FROM todos WHERE id=?", (todo_id,)).fetchone()
    return _row_to_todo(dict(row2))


def _can_see(user_id: str, todo: dict) -> bool:
    if todo.get("created_by") == user_id:
        return True
    if todo.get("assigned_to") == user_id:
        return True
    sw = _loads_list(todo.get("shared_with"))
    return user_id in sw


def _row_to_todo(row: dict) -> dict[str, Any]:
    # Todos are intentionally title-only (no description/notes field).
    return {
        "id": row.get("id"),
        "list_id": row.get("list_id"),
        "title": row.get("title"),
        "done": bool(row.get("done")),
        "due_at": row.get("due_at"),
        "remind_at": row.get("remind_at"),
        "remind_sent_at": row.get("remind_sent_at"),
        "assigned_to": row.get("assigned_to"),
        "shared_with": _loads_list(row.get("shared_with")),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "version": row.get("version"),
    }
