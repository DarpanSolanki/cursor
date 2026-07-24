"""Global live-harness lock — one money e2e at a time (any flow)."""
from __future__ import annotations

import atexit
import fcntl
import os

# Single lock for all flowtest / DCF / RSTCRE pilots.
FLOWTEST_E2E_LOCK = os.environ.get("FLOWTEST_E2E_LOCK", "/tmp/flowtest_e2e.lock")
# Compat: nested restore inside a held lock (DFC historically used DCF_E2E_LOCK_HELD).
_HELD_ENVS = ("FLOWTEST_E2E_LOCK_HELD", "DCF_E2E_LOCK_HELD")


def lock_held() -> bool:
    return any(os.environ.get(k) == "1" for k in _HELD_ENVS)


def mark_lock_held() -> None:
    for k in _HELD_ENVS:
        os.environ[k] = "1"


def acquire_flowtest_lock() -> int:
    """Exclusive non-blocking flock. Returns fd, or -1 if already held by this process tree."""
    if lock_held():
        return -1
    lock_fd = os.open(FLOWTEST_E2E_LOCK, os.O_CREAT | os.O_RDWR, 0o664)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise RuntimeError(
            f"another live harness owns {FLOWTEST_E2E_LOCK}; refusing concurrent run"
        ) from exc
    mark_lock_held()
    atexit.register(os.close, lock_fd)
    return lock_fd


# Back-compat alias used by DCF scripts
acquire_dcf_e2e_lock = acquire_flowtest_lock
DCF_E2E_LOCK = FLOWTEST_E2E_LOCK
