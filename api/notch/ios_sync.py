from __future__ import annotations

import json
import time
import uuid
from typing import Any

from fastapi import HTTPException

from .auth import Principal
from .db import tx
from .lists import ensure_default_list
from .notes import ensure_default_group


def now() -> int:
    return int(time.time())


def _principal_user_id(p: Principal) -> str:
    if p.kind != "user" or not p.user:
        raise HTTPException(status_code=403, detail="User session required")
    return str(p.user["id"])


def _loads_list(value: str | None) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
        return [str(item) for item in loaded] if isinstance(loaded, list) else []
    except Exception:
        return []


def _visible(user_id: str, row: dict[str, Any]) -> bool:
    return row.get("created_by") == user_id or row.get("assigned_to") == user_id or user_id in _loads_list(row.get("shared_with"))


def _validate_uuid(value: Any, field: str) -> str:
    try:
        return str(uuid.UUID(str(value)))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid {field}") from exc


def snapshot(*, p: Principal) -> dict[str, Any]:
    user_id = _principal_user_id(p)
    ensure_default_list(user_id)
    ensure_default_group(user_id)
    with tx() as con:
        lists = [dict(row) for row in con.execute(
            "SELECT * FROM todo_lists WHERE created_by=? OR instr(shared_with, ?) > 0 ORDER BY lower(name)",
            (user_id, user_id),
        ).fetchall()]
        groups = [dict(row) for row in con.execute(
            "SELECT * FROM note_groups WHERE created_by=? OR instr(shared_with, ?) > 0 ORDER BY lower(name)",
            (user_id, user_id),
        ).fetchall()]
        todos = [dict(row) for row in con.execute(
            "SELECT * FROM todos WHERE created_by=? OR assigned_to=? OR instr(shared_with, ?) > 0 ORDER BY updated_at DESC",
            (user_id, user_id, user_id),
        ).fetchall()]
        notes = [dict(row) for row in con.execute(
            """SELECT n.* FROM notes n WHERE n.created_by=? OR instr(n.shared_with, ?) > 0
               OR EXISTS(SELECT 1 FROM note_groups g WHERE g.id=n.group_id AND instr(g.shared_with, ?) > 0)
               ORDER BY n.updated_at DESC""",
            (user_id, user_id, user_id),
        ).fetchall()]

    def collection(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "name": row["name"], "created_by": row["created_by"], "shared_with": _loads_list(row.get("shared_with")), "created_at": row["created_at"], "updated_at": row["updated_at"]}

    def todo(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "list_id": row["list_id"], "title": row["title"], "done": bool(row.get("done")), "due_at": row.get("due_at"), "remind_at": row.get("remind_at"), "created_by": row["created_by"], "shared_with": _loads_list(row.get("shared_with")), "created_at": row["created_at"], "updated_at": row["updated_at"], "deleted_at": row.get("deleted_at"), "version": row.get("version") or 1}

    def note(row: dict[str, Any]) -> dict[str, Any]:
        return {"id": row["id"], "group_id": row["group_id"], "title": row["title"], "body_md": row.get("body_md") or "", "created_by": row["created_by"], "shared_with": _loads_list(row.get("shared_with")), "created_at": row["created_at"], "updated_at": row["updated_at"], "deleted_at": row.get("deleted_at"), "version": row.get("version") or 1}

    return {"ok": True, "server_time": now(), "user": dict(p.user), "todo_lists": [collection(row) for row in lists], "todos": [todo(row) for row in todos], "note_groups": [collection(row) for row in groups], "notes": [note(row) for row in notes]}


def apply_operations(*, p: Principal, payload: dict[str, Any]) -> dict[str, Any]:
    user_id = _principal_user_id(p)
    operations = payload.get("operations")
    if not isinstance(operations, list) or len(operations) > 100:
        raise HTTPException(status_code=400, detail="operations must be a list of at most 100")
    results = []
    for operation in operations:
        if not isinstance(operation, dict):
            raise HTTPException(status_code=400, detail="Invalid operation")
        operation_id = _validate_uuid(operation.get("id"), "operation id")
        entity_id = _validate_uuid(operation.get("entity_id"), "entity id")
        entity_type = str(operation.get("entity_type") or "")
        mutation = str(operation.get("mutation") or "")
        body = operation.get("payload") if isinstance(operation.get("payload"), dict) else {}
        base_version = operation.get("base_version")
        with tx() as con:
            prior = con.execute("SELECT result_json FROM ios_sync_operations WHERE user_id=? AND operation_id=?", (user_id, operation_id)).fetchone()
            if prior:
                results.append(json.loads(prior["result_json"]))
                continue
            result = _apply_one(con, user_id, entity_type, entity_id, mutation, body, base_version)
            con.execute("INSERT INTO ios_sync_operations(user_id,operation_id,applied_at,result_json) VALUES(?,?,?,?)", (user_id, operation_id, now(), json.dumps(result, separators=(",", ":"))))
            results.append(result)
    return {"ok": True, "results": results}


def _require_collection(con, table: str, collection_id: str, user_id: str) -> None:
    row = con.execute(f"SELECT * FROM {table} WHERE id=?", (collection_id,)).fetchone()
    if not row or not _visible(user_id, dict(row)):
        raise HTTPException(status_code=404, detail="Collection not found")


def _apply_one(con, user_id: str, entity_type: str, entity_id: str, mutation: str, body: dict[str, Any], base_version: Any) -> dict[str, Any]:
    if entity_type == "collection":
        return _apply_collection(con, user_id, entity_id, mutation, body)
    if entity_type == "todo":
        return _apply_item(con, user_id, entity_id, mutation, body, base_version, is_note=False)
    if entity_type == "note":
        return _apply_item(con, user_id, entity_id, mutation, body, base_version, is_note=True)
    raise HTTPException(status_code=400, detail="Unsupported entity type")


def _apply_collection(con, user_id: str, entity_id: str, mutation: str, body: dict[str, Any]) -> dict[str, Any]:
    kind = str(body.get("kind_raw") or "")
    if kind not in ("todos", "notes"):
        raise HTTPException(status_code=400, detail="Invalid collection kind")
    table = "todo_lists" if kind == "todos" else "note_groups"
    title = str(body.get("title") or "").strip()
    row = con.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
    current = dict(row) if row else None
    if current and not _visible(user_id, current):
        raise HTTPException(status_code=404, detail="Collection not found")
    if mutation == "create":
        if current:
            return {"id": entity_id, "replayed": True}
        if not title:
            raise HTTPException(status_code=400, detail="Missing title")
        timestamp = now()
        con.execute(f"INSERT INTO {table}(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,?,?)", (entity_id, title, user_id, "[]", timestamp, timestamp))
        return {"id": entity_id, "created": True}
    if not current:
        raise HTTPException(status_code=404, detail="Collection not found")
    if current.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="Only creator can edit")
    if mutation == "update" and title:
        con.execute(f"UPDATE {table} SET name=?,updated_at=? WHERE id=?", (title, now(), entity_id))
        return {"id": entity_id, "updated": True}
    raise HTTPException(status_code=400, detail="Unsupported collection mutation")


def _apply_item(con, user_id: str, entity_id: str, mutation: str, body: dict[str, Any], base_version: Any, *, is_note: bool) -> dict[str, Any]:
    table = "notes" if is_note else "todos"
    row = con.execute(f"SELECT * FROM {table} WHERE id=?", (entity_id,)).fetchone()
    current = dict(row) if row else None
    if current and not _visible(user_id, current):
        raise HTTPException(status_code=404, detail="Item not found")

    if mutation == "create":
        if current:
            return {"id": entity_id, "version": int(current.get("version") or 1), "replayed": True}
        title = str(body.get("title") or "").strip()
        collection_id = _validate_uuid(body.get("collection_id"), "collection id")
        if not title:
            raise HTTPException(status_code=400, detail="Missing title")
        timestamp = now()
        if is_note:
            _require_collection(con, "note_groups", collection_id, user_id)
            con.execute("INSERT INTO notes(id,group_id,title,body_md,shared_with,created_by,created_at,updated_at,version) VALUES(?,?,?,?,?,?,?,?,1)", (entity_id, collection_id, title, str(body.get("body") or ""), "[]", user_id, timestamp, timestamp))
        else:
            _require_collection(con, "todo_lists", collection_id, user_id)
            con.execute("""INSERT INTO todos(id,list_id,title,notes,done,due_at,remind_at,remind_sent_at,assigned_to,shared_with,created_by,created_at,updated_at,version)
                           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)""", (entity_id, collection_id, title, None, int(bool(body.get("completed"))), body.get("due_at"), body.get("reminder_at"), None, None, "[]", user_id, timestamp, timestamp))
        return {"id": entity_id, "version": 1, "created": True}

    if not current:
        raise HTTPException(status_code=404, detail="Item not found")
    if base_version is not None and int(base_version) != int(current.get("version") or 0):
        raise HTTPException(status_code=409, detail={"message": "Version conflict", "id": entity_id, "server_version": current.get("version")})
    if mutation in ("tombstone", "restore") and current.get("created_by") != user_id:
        raise HTTPException(status_code=403, detail="Only creator can delete or restore")

    fields: dict[str, Any] = {}
    if mutation in ("update", "complete"):
        if "title" in body:
            fields["title"] = str(body.get("title") or "").strip()
        if is_note and "body" in body:
            fields["body_md"] = str(body.get("body") or "")
        if not is_note:
            if "completed" in body:
                fields["done"] = int(bool(body.get("completed")))
            if "due_at" in body:
                fields["due_at"] = body.get("due_at")
            if "reminder_at" in body:
                fields["remind_at"] = body.get("reminder_at")
                fields["remind_sent_at"] = None
    elif mutation == "tombstone":
        fields["deleted_at"] = now()
    elif mutation == "restore":
        fields["deleted_at"] = None
    else:
        raise HTTPException(status_code=400, detail="Unsupported mutation")
    if not fields:
        return {"id": entity_id, "version": int(current.get("version") or 1), "unchanged": True}
    assignments = [f"{name}=?" for name in fields]
    values = list(fields.values())
    assignments.extend(["updated_at=?", "version=version+1"])
    values.extend([now(), entity_id])
    con.execute(f"UPDATE {table} SET {', '.join(assignments)} WHERE id=?", values)
    updated = con.execute(f"SELECT version FROM {table} WHERE id=?", (entity_id,)).fetchone()
    return {"id": entity_id, "version": int(updated["version"]), "updated": True}
