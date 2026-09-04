import json
import os
import tempfile
import unittest
import uuid


_temp = tempfile.TemporaryDirectory()
os.environ["DB_PATH"] = os.path.join(_temp.name, "notch.db")
os.environ.setdefault("SESSION_SECRET", "test-session-secret")
os.environ.setdefault("SERVICE_TOKEN", "test-service-token")
os.environ.setdefault("SCHEDULER_ENABLED", "false")

from fastapi import HTTPException

from notch import ios_sync, schema, todos
from notch.auth import Principal
from notch.db import tx


class IOSSharingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        schema.apply_schema()

    def setUp(self):
        with tx() as con:
            for table in ("ios_sync_operations", "todos", "notes", "todo_lists", "note_groups", "sessions", "users"):
                con.execute(f"DELETE FROM {table}")
            self.owner_id = str(uuid.uuid4())
            self.friend_id = str(uuid.uuid4())
            self.third_id = str(uuid.uuid4())
            for user_id, handle, name in (
                (self.owner_id, "owner", "Owner"),
                (self.friend_id, "friend", "Friend"),
                (self.third_id, "third", "Third"),
            ):
                con.execute(
                    "INSERT INTO users(id,handle,display_name,password_hash,created_at,updated_at) VALUES(?,?,?,?,1,1)",
                    (user_id, handle, name, "not-returned"),
                )
            self.list_id = str(uuid.uuid4())
            self.todo_id = str(uuid.uuid4())
            self.group_id = str(uuid.uuid4())
            self.note_id = str(uuid.uuid4())
            con.execute(
                "INSERT INTO todo_lists(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,1,1)",
                (self.list_id, "Packing", self.owner_id, "[]"),
            )
            con.execute(
                "INSERT INTO todos(id,list_id,title,done,shared_with,created_by,created_at,updated_at,version) VALUES(?,?,?,0,?,?,1,1,1)",
                (self.todo_id, self.list_id, "Passport", "[]", self.owner_id),
            )
            con.execute(
                "INSERT INTO note_groups(id,name,created_by,shared_with,created_at,updated_at) VALUES(?,?,?,?,1,1)",
                (self.group_id, "Trip", self.owner_id, "[]"),
            )
            con.execute(
                "INSERT INTO notes(id,group_id,title,body_md,shared_with,created_by,created_at,updated_at,version) VALUES(?,?,?,?,?,?,1,1,1)",
                (self.note_id, self.group_id, "Cabin", "Deck 8", "[]", self.owner_id),
            )
        self.owner = Principal("user", {"id": self.owner_id, "handle": "owner", "display_name": "Owner"})
        self.friend = Principal("user", {"id": self.friend_id, "handle": "friend", "display_name": "Friend"})
        self.third = Principal("user", {"id": self.third_id, "handle": "third", "display_name": "Third"})

    def operation(self, principal, entity_type, entity_id, payload, base_version=None, mutation="update"):
        return ios_sync.apply_operations(
            p=principal,
            payload={"operations": [{
                "id": str(uuid.uuid4()),
                "entity_id": entity_id,
                "entity_type": entity_type,
                "mutation": mutation,
                "base_version": base_version,
                "payload": payload,
            }]},
        )

    def test_snapshot_directory_is_safe_and_todo_list_share_inherits_children(self):
        owner_snapshot = ios_sync.snapshot(p=self.owner)
        self.assertEqual(owner_snapshot["user"]["id"], self.owner_id)
        self.assertEqual(len(owner_snapshot["users"]), 3)
        self.assertNotIn("password_hash", json.dumps(owner_snapshot))
        self.assertFalse(ios_sync.snapshot(p=self.friend)["todos"])

        self.operation(
            self.owner,
            "collection",
            self.list_id,
            {"kind_raw": "todos", "shared_with": [self.friend_id]},
        )
        friend_snapshot = ios_sync.snapshot(p=self.friend)
        self.assertIn(self.list_id, [row["id"] for row in friend_snapshot["todo_lists"]])
        self.assertEqual([row["id"] for row in friend_snapshot["todos"]], [self.todo_id])
        self.assertEqual([row["id"] for row in todos.list_todos(p=self.friend, query=None, include_done=True)], [self.todo_id])

        result = self.operation(self.friend, "todo", self.todo_id, {"title": "Passport wallet"}, base_version=1)
        self.assertEqual(result["results"][0]["version"], 2)

    def test_group_share_inherits_notes_and_only_owner_changes_people(self):
        self.operation(
            self.owner,
            "collection",
            self.group_id,
            {"kind_raw": "notes", "shared_with": [self.friend_id]},
        )
        self.assertEqual([row["id"] for row in ios_sync.snapshot(p=self.friend)["notes"]], [self.note_id])

        with self.assertRaises(HTTPException) as caught:
            self.operation(self.friend, "note", self.note_id, {"shared_with": [self.third_id]}, base_version=1)
        self.assertEqual(caught.exception.status_code, 403)

    def test_shared_list_collaborator_can_complete_delete_and_restore_todo(self):
        self.operation(
            self.owner,
            "collection",
            self.list_id,
            {"kind_raw": "todos", "shared_with": [self.friend_id]},
        )
        completed = self.operation(self.friend, "todo", self.todo_id, {"completed": True}, base_version=1)
        self.assertEqual(completed["results"][0]["version"], 2)
        deleted = self.operation(self.friend, "todo", self.todo_id, {}, base_version=2, mutation="tombstone")
        self.assertEqual(deleted["results"][0]["version"], 3)
        restored = self.operation(self.friend, "todo", self.todo_id, {}, base_version=3, mutation="restore")
        self.assertEqual(restored["results"][0]["version"], 4)
        visible = ios_sync.snapshot(p=self.owner)["todos"][0]
        self.assertTrue(visible["done"])
        self.assertIsNone(visible["deleted_at"])

    def test_assignment_alone_does_not_grant_todo_delete_and_notes_stay_owner_only(self):
        self.operation(self.owner, "todo", self.todo_id, {"assigned_to": self.third_id}, base_version=1)
        with self.assertRaises(HTTPException) as todo_error:
            self.operation(self.third, "todo", self.todo_id, {}, base_version=2, mutation="tombstone")
        self.assertEqual(todo_error.exception.status_code, 403)

        self.operation(
            self.owner,
            "collection",
            self.group_id,
            {"kind_raw": "notes", "shared_with": [self.friend_id]},
        )
        with self.assertRaises(HTTPException) as note_error:
            self.operation(self.friend, "note", self.note_id, {}, base_version=1, mutation="tombstone")
        self.assertEqual(note_error.exception.status_code, 403)

    def test_owner_can_assign_todo_and_clear_assignment(self):
        self.operation(
            self.owner,
            "todo",
            self.todo_id,
            {"assigned_to": self.third_id, "shared_with": [self.friend_id]},
            base_version=1,
        )
        third_todo = ios_sync.snapshot(p=self.third)["todos"][0]
        self.assertEqual(third_todo["assigned_to"], self.third_id)
        self.assertEqual(third_todo["shared_with"], [self.friend_id])

        self.operation(self.owner, "todo", self.todo_id, {"clear_assigned_to": True}, base_version=2)
        self.assertFalse(ios_sync.snapshot(p=self.third)["todos"])

    def test_unknown_user_is_rejected(self):
        with self.assertRaises(HTTPException) as caught:
            self.operation(
                self.owner,
                "collection",
                self.list_id,
                {"kind_raw": "todos", "shared_with": [str(uuid.uuid4())]},
            )
        self.assertEqual(caught.exception.status_code, 400)


if __name__ == "__main__":
    unittest.main()
