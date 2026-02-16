from __future__ import annotations

from pathlib import Path

from .db import tx


def _try(con, sql: str) -> None:
    try:
        con.execute(sql)
    except Exception:
        # best-effort migration; safe to ignore if already applied
        pass


def apply_schema() -> None:
    sql_path = Path(__file__).with_name("schema.sql")
    sql = sql_path.read_text("utf-8")
    with tx() as con:
        con.executescript(sql)

        # Best-effort migrations for early-stage schema changes.
        # (SQLite doesn't support ALTER TABLE .. ADD COLUMN IF NOT EXISTS in all versions.)
        _try(con, "ALTER TABLE todos ADD COLUMN list_id TEXT")
        _try(con, "ALTER TABLE notes ADD COLUMN group_id TEXT")
