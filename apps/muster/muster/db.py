"""SQLite on the board. One JSON blob per record keeps the schema flexible during the hackathon."""
import json
import sqlite3
import threading

from . import config
from .schema import Record

_lock = threading.Lock()
_conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
_conn.execute("CREATE TABLE IF NOT EXISTS records (id INTEGER PRIMARY KEY, body TEXT)")
_conn.commit()


def next_id() -> int:
    with _lock:
        return _conn.execute("SELECT COALESCE(MAX(id),0)+1 FROM records").fetchone()[0]


def save(rec: Record) -> None:
    with _lock:
        _conn.execute("INSERT OR REPLACE INTO records VALUES (?,?)",
                      (rec.id, json.dumps(rec.to_dict(), ensure_ascii=False)))
        _conn.commit()


def all_records() -> list[Record]:
    with _lock:
        rows = _conn.execute("SELECT body FROM records ORDER BY id").fetchall()
    return [Record.from_dict(json.loads(b)) for (b,) in rows]


def reset() -> None:
    with _lock:
        _conn.execute("DELETE FROM records")
        _conn.commit()
