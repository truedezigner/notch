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


def ensure_default_group(user_id: str) -> dict[str, Any]:
    with tx() as con:
        row = con.execute(
            "SELECT * FROM note_groups WHERE created_by=? AND lower(name)=lower(?) LIMIT 1",
            (user_id, "General"),
        ).fetchone()
        if row:
            return _row_to_group(dict(row))
        gid = str(uuid.uuid4())
        t = now()
        con.execute(
            "INSERT INTO note_groups(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (gid, "General", user_id, _dumps_list([]), t, t),
        )
        row2 = con.execute("SELECT * FROM note_groups WHERE id=?", (gid,)).fetchone()
        return _row_to_group(dict(row2))


def list_groups(*, p: Principal) -> list[dict[str, Any]]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    ensure_default_group(p.user["id"])
    with tx() as con:
        rows = con.execute(
            "SELECT * FROM note_groups WHERE created_by=? OR instr(shared_with, ?) > 0 ORDER BY lower(name) ASC",
            (p.user["id"], p.user["id"]),
        ).fetchall()
    return [_row_to_group(dict(r)) for r in rows]


def create_group(*, p: Principal, payload: dict) -> dict[str, Any]:
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

    gid = str(uuid.uuid4())
    t = now()
    with tx() as con:
        con.execute(
            "INSERT INTO note_groups(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,?,?)",
            (gid, name, p.user["id"], _dumps_list([str(x) for x in shared_with]), t, t),
        )
        row = con.execute("SELECT * FROM note_groups WHERE id=?", (gid,)).fetchone()
    return _row_to_group(dict(row))


def list_notes(*, p: Principal, query: str | None, group_id: str | None, limit: int = 200) -> list[dict[str, Any]]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    q = (query or "").strip().lower()
    params: list[Any] = []
    where = ["(created_by=? OR instr(shared_with, ?) > 0)"]
    params.extend([p.user["id"], p.user["id"]])

    if group_id:
        where.append("group_id=?")
        params.append(str(group_id))

    if q:
        where.append("(lower(title) LIKE ? OR lower(body_md) LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%"])

    sql = "SELECT * FROM notes WHERE " + " AND ".join(where) + " ORDER BY updated_at DESC LIMIT ?"
    params.append(int(limit))

    with tx() as con:
        rows = con.execute(sql, params).fetchall()
    return [_row_to_note(dict(r)) for r in rows]


def create_note(*, p: Principal, payload: dict) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    title = (payload.get("title") or "").strip()
    body_md = payload.get("body_md")
    if body_md is None:
        body_md = ""
    body_md = str(body_md)

    if not title:
        raise HTTPException(status_code=400, detail="Missing title")

    group_id = payload.get("group_id")
    if not group_id:
        group = ensure_default_group(p.user["id"])
        group_id = group["id"]

    shared_with = payload.get("shared_with")
    if shared_with is None:
        shared_with = []
    if not isinstance(shared_with, list):
        raise HTTPException(status_code=400, detail="shared_with must be list")

    nid = str(uuid.uuid4())
    t = now()
    with tx() as con:
        con.execute(
            """
            INSERT INTO notes(id,group_id,title,body_md,shared_with,created_by,created_at,updated_at,version)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (nid, str(group_id), title, body_md, _dumps_list([str(x) for x in shared_with]), p.user["id"], t, t, 1),
        )
        row = con.execute("SELECT * FROM notes WHERE id=?", (nid,)).fetchone()
    return _row_to_note(dict(row))


def get_note(*, p: Principal, note_id: str) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")
    with tx() as con:
        row = con.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        note = dict(row)
    if not _can_see(p.user["id"], note):
        raise HTTPException(status_code=404, detail="Not found")
    return _row_to_note(note)


def patch_note(*, p: Principal, note_id: str, payload: dict) -> dict[str, Any]:
    if p.kind != "user":
        raise HTTPException(status_code=403, detail="User session required")

    if_version = payload.get("if_version")
    if if_version is not None:
        try:
            if_version = int(if_version)
        except Exception:
            raise HTTPException(status_code=400, detail="if_version must be int")

    fields: dict[str, Any] = {}
    for k in ("title", "body_md"):
        if k in payload:
            v = payload.get(k)
            fields[k] = "" if v is None else str(v)

    if "shared_with" in payload:
        v = payload.get("shared_with")
        if not isinstance(v, list):
            raise HTTPException(status_code=400, detail="shared_with must be list")
        fields["shared_with"] = _dumps_list([str(x) for x in v])

    if "group_id" in payload:
        v = payload.get("group_id")
        fields["group_id"] = None if (v is None or v == "") else str(v)

    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    with tx() as con:
        row = con.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Not found")
        cur = dict(row)
        if not _can_see(p.user["id"], cur):
            raise HTTPException(status_code=404, detail="Not found")
        if if_version is not None and int(cur.get("version") or 0) != if_version:
            raise HTTPException(status_code=409, detail="Version conflict")

        sets = []
        params: list[Any] = []
        for k, v in fields.items():
            sets.append(f"{k}=?")
            params.append(v)
        sets.append("updated_at=?")
        params.append(now())
        sets.append("version=version+1")
        params.append(note_id)
        con.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id=?", params)
        row2 = con.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone()
    return _row_to_note(dict(row2))


def _can_see(user_id: str, note: dict) -> bool:
    if note.get("created_by") == user_id:
        return True
    sw = _loads_list(note.get("shared_with"))
    return user_id in sw


def _row_to_group(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "created_by": row.get("created_by"),
        "shared_with": _loads_list(row.get("shared_with")),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def _row_to_note(row: dict) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "group_id": row.get("group_id"),
        "title": row.get("title"),
        "body_md": row.get("body_md"),
        "shared_with": _loads_list(row.get("shared_with")),
        "created_by": row.get("created_by"),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "version": row.get("version"),
    }
