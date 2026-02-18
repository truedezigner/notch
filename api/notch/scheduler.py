from __future__ import annotations

import json
import time
import uuid

from .db import tx
from .ntfy import publish, topic_for_handle
from .settings import settings


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


async def run_once() -> int:
    """Find due reminders and send notifications.

    Returns number processed (attempted).
    """
    if not settings.SCHEDULER_ENABLED:
        return 0

    due = []
    with tx() as con:
        rows = con.execute(
            """
            SELECT * FROM todos
            WHERE done=0
              AND remind_at IS NOT NULL
              AND remind_at <= ?
              AND remind_sent_at IS NULL
            ORDER BY remind_at ASC
            LIMIT 25
            """,
            (now(),),
        ).fetchall()
        due = [dict(r) for r in rows]

    processed = 0
    for todo in due:
        processed += 1
        await _notify_for_todo(todo)
    return processed


async def _notify_for_todo(todo: dict) -> None:
    todo_id = todo["id"]

    # Determine recipients (user ids)
    # If assigned_to is set AND shared_with has entries, notify everyone.
    recipients_set: set[str] = set()
    if todo.get("assigned_to"):
        recipients_set.add(str(todo["assigned_to"]))
    for uid in _loads_list(todo.get("shared_with")):
        if uid:
            recipients_set.add(str(uid))
    recipients: list[str] = [r for r in recipients_set if r]

    # If nobody to notify, mark sent so we don't loop.
    if not recipients:
        with tx() as con:
            con.execute("UPDATE todos SET remind_sent_at=? WHERE id=?", (now(), todo_id))
        return

    # Resolve handles
    with tx() as con:
        user_rows = con.execute(
            f"SELECT id,handle,display_name FROM users WHERE id IN ({','.join('?' for _ in recipients)})",
            recipients,
        ).fetchall()
        users = {r["id"]: dict(r) for r in user_rows}

    title = "Reminder"
    message = (todo.get("title") or "").strip() or "(untitled)"
    click = settings.APP_BASE_URL.rstrip("/") + f"/app/todos/{todo_id}"

    any_error = False
    last_error = None

    for uid in recipients:
        u = users.get(uid)
        if not u:
            continue
        topic = topic_for_handle(u["handle"])
        outbox_id = str(uuid.uuid4())
        t = now()
        with tx() as con:
            con.execute(
                """
                INSERT INTO outbox_notifications(id,user_id,topic,title,message,click_url,priority,tags,status,last_error,created_at,sent_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (outbox_id, uid, topic, title, message, click, None, json.dumps(["todo"], ensure_ascii=False), "pending", None, t, None),
            )

        try:
            await publish(topic=topic, title=title, message=message, click_url=click, tags=["todo"])
            with tx() as con:
                con.execute(
                    "UPDATE outbox_notifications SET status=?, sent_at=? WHERE id=?",
                    ("sent", now(), outbox_id),
                )
        except Exception as exc:
            any_error = True
            last_error = str(exc)
            with tx() as con:
                con.execute(
                    "UPDATE outbox_notifications SET status=?, last_error=? WHERE id=?",
                    ("error", last_error, outbox_id),
                )

    if not any_error:
        with tx() as con:
            con.execute("UPDATE todos SET remind_sent_at=? WHERE id=?", (now(), todo_id))
    else:
        # Leave unsent so we can retry later; but avoid hammering: push it forward a bit.
        with tx() as con:
            con.execute("UPDATE todos SET remind_at=? WHERE id=?", (now() + 30, todo_id))
