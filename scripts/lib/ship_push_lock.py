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


def update_pending_ship(root: Path, mutator, pending_path: Path | None = None) -> None:
    """
    Update `.cursor/.pending-ship-work.json` safely.

    `mutator` is a callable: dict -> dict (may mutate in-place and/or return a new dict).
    This helper exists because several ship-loop scripts share the same contract.
    """

    pending_path = pending_path or (Path(root) / ".cursor/.pending-ship-work.json")
    if not pending_path.is_file():
        return

    import json

    data = json.loads(pending_path.read_text(encoding="utf-8") or "{}")
    updated = mutator(data)
    if updated is None:
        updated = data

    pending_path.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
