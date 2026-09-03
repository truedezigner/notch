"""Copied-database two-user proof for the running candidate container."""

from __future__ import annotations

import concurrent.futures
import json
import os
import secrets
import sqlite3
import time
import uuid

import httpx


base_url = os.environ.get("NOTCH_TEST_BASE_URL", "http://127.0.0.1:8080")
db_path = os.environ["DB_PATH"]
now = int(time.time())

con = sqlite3.connect(db_path)
con.row_factory = sqlite3.Row
users = con.execute("SELECT id FROM users ORDER BY created_at").fetchall()
assert len(users) >= 2, "two users are required"
owner_id, friend_id = str(users[0]["id"]), str(users[1]["id"])
tokens = {owner_id: secrets.token_urlsafe(32), friend_id: secrets.token_urlsafe(32)}
for user_id, token in tokens.items():
    con.execute(
        "INSERT INTO sessions(token,user_id,created_at,expires_at,last_seen_at) VALUES(?,?,?,?,?)",
        (token, user_id, now, now + 600, now),
    )
con.commit()


def headers(user_id: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens[user_id]}"}


try:
    with httpx.Client(base_url=base_url, timeout=15.0) as client:
        assert client.get("/api/ios/v1/changes", params={"since": 0}).status_code == 401
        owner_snapshot = client.get("/api/ios/v1/snapshot", headers=headers(owner_id)).raise_for_status().json()
        friend_snapshot = client.get("/api/ios/v1/snapshot", headers=headers(friend_id)).raise_for_status().json()
        friend_todo_ids = {row["id"] for row in friend_snapshot["todos"]}
        todo = next(row for row in owner_snapshot["todos"] if row["id"] in friend_todo_ids and row.get("deleted_at") is None)
        initial_done = bool(todo["done"])
        friend_revision = int(friend_snapshot["change_revision"])

        def wait_for_change() -> dict:
            with httpx.Client(base_url=base_url, timeout=15.0) as waiting_client:
                return waiting_client.get(
                    "/api/ios/v1/changes",
                    params={"since": friend_revision, "timeout_seconds": 10},
                    headers=headers(friend_id),
                ).raise_for_status().json()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            started = time.monotonic()
            waiter = executor.submit(wait_for_change)
            time.sleep(0.1)
            operation = {
                "operations": [{
                    "id": str(uuid.uuid4()),
                    "entity_id": todo["id"],
                    "entity_type": "todo",
                    "mutation": "complete",
                    "base_version": todo["version"],
                    "payload": {"completed": not initial_done},
                }]
            }
            applied = client.post("/api/ios/v1/operations", json=operation, headers=headers(owner_id)).raise_for_status().json()
            signal = waiter.result(timeout=2.0)
            latency = time.monotonic() - started - 0.1

        refreshed = client.get("/api/ios/v1/snapshot", headers=headers(friend_id)).raise_for_status().json()
        refreshed_todo = next(row for row in refreshed["todos"] if row["id"] == todo["id"])
        assert signal["changed"] is True
        assert signal["revision"] == applied["change_revision"]
        assert bool(refreshed_todo["done"]) is not initial_done
        assert latency < 1.0, f"wake-up took {latency:.3f}s"
        client.post(
            "/api/ios/v1/operations",
            json={"operations": [{
                "id": str(uuid.uuid4()),
                "entity_id": todo["id"],
                "entity_type": "todo",
                "mutation": "complete",
                "base_version": refreshed_todo["version"],
                "payload": {"completed": initial_done},
            }]},
            headers=headers(owner_id),
        ).raise_for_status()
        print(json.dumps({"ok": True, "wake_latency_ms": round(latency * 1000), "friend_received_completion": True}))
finally:
    con.execute("DELETE FROM sessions WHERE token IN (?,?)", tuple(tokens.values()))
    con.commit()
    con.close()
