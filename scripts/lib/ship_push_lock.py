#!/usr/bin/env python3
"""File lock for ship-and-continue — prevent concurrent push/close races."""
from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LOCK_PATH = ROOT / ".cursor/.ship-push.lock"
DEFAULT_TIMEOUT_SEC = 10


@contextmanager
def ship_push_lock(timeout_sec: int = DEFAULT_TIMEOUT_SEC):
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(LOCK_PATH), os.O_CREAT | os.O_RDWR, 0o644)
    acquired = False
    try:
        import fcntl

        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except BlockingIOError:
                time.sleep(0.2)
        if not acquired:
            yield False
            return
        yield True
    finally:
        if acquired:
            try:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_UN)
            except Exception:
                pass
        os.close(fd)
