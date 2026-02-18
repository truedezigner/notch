from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import HTTPException

from .auth import Principal
from .db import tx


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


def ensure_default_list(user_id: str) -> dict[str, Any]:
    """Ensure an Inbox list exists for a user; return it."""
    with tx() as con:
        row = con.execute(
            "SELECT * FROM todo_lists WHERE created_by=? AND lower(name)=lower(?) LIMIT 1",
            (user_id, "Inbox"),
        ).fetchone()
        if row:
            return _row_to_list(dict(row))

        lid = str(uuid.uuid4())
        t = now()
        con.execute(
            "INSERT INTO todo_lists(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (lid, "Inbox", user_id, _dumps_list([]), t, t),
        )
        row2 = con.execute("SELECT * FROM todo_lists WHERE id=?", (lid,)).fetchone()
        return _row_to_list(dict(row2))


def create_list(*, p: Principal, payload: dict) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    name = (payload.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Missing name")
    shared_with = payload.get("shared_with")
    if shared_with is None:
        shared_with = []
    if not isinstance(shared_with, list):
        raise HTTPException(status_code=400, detail="shared_with must be list")

    lid = str(uuid.uuid4())
    t = now()
    with tx() as con:
        con.execute(
            "INSERT INTO todo_lists(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (lid, name, p.user["id"], _dumps_list([str(x) for x in shared_with]), t, t),
        )
        row = con.execute("SELECT * FROM todo_lists WHERE id=?", (lid,)).fetchone()
    return _row_to_list(dict(row))


def delete_list(*, p: Principal, list_id: str) -> dict[str, Any]:
    """Delete a todo list without deleting its todos.

    Todos are reassigned to the user's Inbox list.
    Only the list creator may delete.
    """
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    # Ensure Inbox exists
    inbox = ensure_default_list(p.user["id"])

    with tx() as con:
        row = con.execute("SELECT * FROM todo_lists WHERE id=?", (str(list_id),)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)

        if cur.get("created_by") != p.user["id"]:
            raise HTTPException(status_code=403, detail="Only creator can delete")

        # Don't allow deleting Inbox itself
        if str(cur.get("id")) == str(inbox.get("id")) or str(cur.get("name") or "").strip().lower() == "inbox":
            raise HTTPException(status_code=409, detail="Cannot delete Inbox")

        # Reassign todos first
        con.execute(
            "UPDATE todos SET list_id=?, updated_at=? WHERE list_id=?",
            (str(inbox["id"]), now(), str(list_id)),
        )

        # Delete list
        con.execute("DELETE FROM todo_lists WHERE id=?", (str(list_id),))

    return {"ok": True, "deleted": True, "id": str(list_id), "moved_todos_to": inbox.get("id")}


def list_lists(*, p: Principal) -> list[dict[str, Any]]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    # Ensure Inbox exists
    ensure_default_list(p.user["id"])

    with tx() as con:
        rows = con.execute(
            """
            SELECT * FROM todo_lists
            WHERE created_by=? OR instr(shared_with, ?) > 0
            ORDER BY lower(name) ASC
            """,
            (p.user["id"], p.user["id"]),
        ).fetchall()
    return [_row_to_list(dict(r)) for r in rows]


def _row_to_list(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "created_by": row.get("created_by"),
        "shared_with": _loads_list(row.get("shared_with")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }
