from __future__ import annotations

from pathlib import Path

from .db import tx


def apply_schema() -> None:
    sql_path = Path(__file__).with_name("schema.sql")
    sql = sql_path.read_text("utf-8")
    with tx() as con:
        con.executescript(sql)
