"""Flushed JSONL decision log - judges ask to see local inputs, decisions, actions, errors."""
import json
import time
from contextlib import contextmanager
from datetime import datetime

from . import config

_recent: list[dict] = []


def write(stage: str, **fields) -> dict:
    entry = {"t": datetime.now().strftime("%H:%M:%S.%f")[:-3], "stage": stage, **fields}
    with open(config.LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
        f.flush()
    _recent.append(entry)
    del _recent[:-200]
    return entry


@contextmanager
def timed(stage: str, **fields):
    """with log.timed("extract", backend=...) as out: out["result"] = ...  -> logs ms + result/error"""
    out: dict = {}
    t0 = time.perf_counter()
    try:
        yield out
    except Exception as e:
        write(stage, ms=round((time.perf_counter() - t0) * 1000, 1), error=f"{type(e).__name__}: {e}", **fields)
        raise
    write(stage, ms=round((time.perf_counter() - t0) * 1000, 1), **fields, **out)


def recent(n: int = 40) -> list[dict]:
    return _recent[-n:]
