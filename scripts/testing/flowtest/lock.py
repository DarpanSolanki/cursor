"""Global live-harness lock — one money e2e at a time (any flow)."""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Any

# Single lock for all flowtest / DCF / RSTCRE pilots.
FLOWTEST_E2E_LOCK = os.environ.get("FLOWTEST_E2E_LOCK", "/tmp/flowtest_e2e.lock")
# Compat: nested restore inside a held lock (DFC historically used DCF_E2E_LOCK_HELD).
_HELD_ENVS = ("FLOWTEST_E2E_LOCK_HELD", "DCF_E2E_LOCK_HELD")
_DEFAULT_WAIT_S = 120.0
_POLL_S = 0.5


def lock_held() -> bool:
    return any(os.environ.get(k) == "1" for k in _HELD_ENVS)


def mark_lock_held() -> None:
    for k in _HELD_ENVS:
        os.environ[k] = "1"


def _wait_seconds() -> float:
    raw = os.environ.get("FLOWTEST_LOCK_WAIT_S", str(int(_DEFAULT_WAIT_S)))
    try:
        return max(0.0, float(raw))
    except ValueError:
        return _DEFAULT_WAIT_S


def _short_cmdline(limit: int = 160) -> str:
    try:
        with open(f"/proc/{os.getpid()}/cmdline", "rb") as fh:
            raw = fh.read().replace(b"\x00", b" ").decode("utf-8", "replace").strip()
        return (raw[:limit] + "…") if len(raw) > limit else raw
    except OSError:
        return " ".join(sys.argv)[:limit]


def _case_id() -> str:
    for key in ("FLOWTEST_CASE_ID", "NTEST_CASE_ID", "NTEST_ID"):
        val = (os.environ.get(key) or "").strip()
        if val:
            return val
    return ""


def _owner_payload() -> dict[str, Any]:
    return {
        "pid": os.getpid(),
        "case": _case_id() or "-",
        "started_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cmdline": _short_cmdline(),
    }


def write_owner_meta(lock_fd: int) -> None:
    """Write owner lines into the lock file (holder already has exclusive flock)."""
    payload = _owner_payload()
    body = (
        f"pid={payload['pid']}\n"
        f"case={payload['case']}\n"
        f"started_at={payload['started_at']}\n"
        f"cmdline={payload['cmdline']}\n"
        f"json={json.dumps(payload, separators=(',', ':'))}\n"
    )
    os.ftruncate(lock_fd, 0)
    os.lseek(lock_fd, 0, os.SEEK_SET)
    os.write(lock_fd, body.encode("utf-8"))
    try:
        os.fsync(lock_fd)
    except OSError:
        pass


def read_owner_meta(path: str | None = None) -> dict[str, str]:
    """Best-effort read of owner metadata (works while another process holds flock)."""
    lock_path = path or FLOWTEST_E2E_LOCK
    out: dict[str, str] = {}
    try:
        with open(lock_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                if key == "json":
                    try:
                        data = json.loads(val)
                        for k, v in data.items():
                            out.setdefault(str(k), str(v))
                    except json.JSONDecodeError:
                        pass
                    continue
                out[key] = val
    except OSError:
        pass
    return out


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def flock_held(path: str | None = None) -> bool:
    """True if another process currently holds an exclusive flock on the lock file."""
    lock_path = path or FLOWTEST_E2E_LOCK
    if not os.path.exists(lock_path):
        return False
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o664)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def format_owner_busy(path: str | None = None) -> str:
    lock_path = path or FLOWTEST_E2E_LOCK
    meta = read_owner_meta(lock_path)
    pid = meta.get("pid", "?")
    case = meta.get("case", "?")
    started = meta.get("started_at", "?")
    alive = ""
    try:
        alive = " live" if _pid_alive(int(pid)) else " dead?"
    except (TypeError, ValueError):
        pass
    return (
        f"another live harness owns {lock_path}; "
        f"pid={pid}{alive} case={case} started={started}"
    )


def lock_status(path: str | None = None) -> dict[str, Any]:
    """Agent helper: held Y/N + owner fields."""
    lock_path = path or FLOWTEST_E2E_LOCK
    held = flock_held(lock_path)
    meta = read_owner_meta(lock_path) if os.path.exists(lock_path) else {}
    pid_s = meta.get("pid", "")
    pid_live: bool | None = None
    if pid_s.isdigit():
        pid_live = _pid_alive(int(pid_s))
    return {
        "path": lock_path,
        "held": held,
        "file_exists": os.path.exists(lock_path),
        "pid": pid_s or None,
        "pid_live": pid_live,
        "case": meta.get("case"),
        "started_at": meta.get("started_at"),
        "cmdline": meta.get("cmdline"),
        "self_held": lock_held(),
    }


def acquire_flowtest_lock() -> int:
    """Exclusive flock with optional bounded wait. Returns fd, or -1 if re-entrant."""
    if lock_held():
        return -1
    wait_s = _wait_seconds()
    lock_fd = os.open(FLOWTEST_E2E_LOCK, os.O_CREAT | os.O_RDWR, 0o664)
    deadline = time.monotonic() + wait_s
    while True:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            break
        except BlockingIOError as exc:
            now = time.monotonic()
            if wait_s <= 0 or now >= deadline:
                os.close(lock_fd)
                raise RuntimeError(format_owner_busy(FLOWTEST_E2E_LOCK)) from exc
            time.sleep(_POLL_S)
    write_owner_meta(lock_fd)
    mark_lock_held()
    atexit.register(os.close, lock_fd)
    return lock_fd


# Back-compat alias used by DCF scripts
acquire_dcf_e2e_lock = acquire_flowtest_lock
DCF_E2E_LOCK = FLOWTEST_E2E_LOCK
