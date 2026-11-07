"""SQLite persistence for permit applications."""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

DB_PATH = Path(os.environ.get("PERMITPILOT_DB", Path(__file__).parent.parent / "permitpilot.db"))
_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    address TEXT NOT NULL,
    parcel TEXT NOT NULL,
    applicant_name TEXT NOT NULL,
    applicant_email TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    params TEXT NOT NULL,
    review TEXT NOT NULL,
    extraction_source TEXT NOT NULL,
    status TEXT NOT NULL,
    letter TEXT,
    letter_source TEXT,
    decided_at TEXT,
    history TEXT NOT NULL DEFAULT '[]'
);
"""

JSON_FIELDS = ("parcel", "params", "review", "history")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init(db_path: Optional[Path] = None) -> None:
    global DB_PATH
    if db_path is not None:
        DB_PATH = Path(db_path)
    with _lock, _conn() as c:
        c.executescript(SCHEMA)


def _row(r: sqlite3.Row) -> dict:
    d = dict(r)
    for k in JSON_FIELDS:
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def insert(app: dict) -> dict:
    app = dict(app)
    app.setdefault("created_at", now())
    app.setdefault("history", [{"at": app["created_at"], "event": "Submitted and auto-reviewed"}])
    cols = ["created_at", "address", "parcel", "applicant_name", "applicant_email", "description",
            "params", "review", "extraction_source", "status", "letter", "letter_source", "decided_at", "history"]
    vals = [json.dumps(app.get(k)) if k in JSON_FIELDS else app.get(k) for k in cols]
    with _lock, _conn() as c:
        cur = c.execute(f"INSERT INTO applications ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})", vals)
        new_id = cur.lastrowid
    return get(new_id)


def get(app_id: int) -> Optional[dict]:
    with _conn() as c:
        r = c.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    return _row(r) if r else None


def list_all() -> List[dict]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM applications ORDER BY created_at ASC").fetchall()
    return [_row(r) for r in rows]


def update(app_id: int, **fields) -> Optional[dict]:
    if not fields:
        return get(app_id)
    sets = ", ".join(f"{k} = ?" for k in fields)
    vals = [json.dumps(v) if k in JSON_FIELDS else v for k, v in fields.items()]
    with _lock, _conn() as c:
        c.execute(f"UPDATE applications SET {sets} WHERE id = ?", (*vals, app_id))
    return get(app_id)


def count() -> int:
    with _conn() as c:
        return c.execute("SELECT COUNT(*) FROM applications").fetchone()[0]


def clear() -> None:
    with _lock, _conn() as c:
        c.execute("DELETE FROM applications")
