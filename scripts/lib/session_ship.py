#!/usr/bin/env python3
"""Session-scoped ship touch — avoid auto-close on stale pending or analysis-only tabs."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SESSION_TOUCH = ROOT / ".cursor/.session-ship-touched.json"
AUTOPILOT_STATE = ROOT / ".cursor/.autopilot-state.json"
PENDING = ROOT / ".cursor/.pending-ship-work.json"
PASSED = ROOT / ".cursor/.ship-loop-passed.json"
PUSH_QUEUE = ROOT / ".cursor/.ship-push-queue.json"

TIER_RANK = {"workspace": 0, "service": 1, "money": 2}
SESSION_MAX_AGE_SEC = int(os.environ.get("SESSION_SHIP_MAX_AGE_SEC", str(8 * 3600)))
VERIFY_MAX_AGE_SEC = int(os.environ.get("SESSION_SHIP_VERIFY_MAX_AGE_SEC", str(2 * 3600)))


def _load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def touch_session_ship(root: Path | None = None, *, source: str = "edit", paths: list[str] | None = None) -> None:
    root = root or ROOT
    touch = root / ".cursor/.session-ship-touched.json"
    touch.parent.mkdir(parents=True, exist_ok=True)
    data = _load_json(touch)
    data["touched_at"] = time.time()
    data["source"] = source
    if paths:
        merged = list(dict.fromkeys((data.get("paths") or []) + list(paths)))
        data["paths"] = merged[-20:]
    touch.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def clear_session_ship(root: Path | None = None) -> None:
    root = root or ROOT
    p = root / ".cursor/.session-ship-touched.json"
    if p.is_file():
        p.unlink()


def session_ship_active(root: Path | None = None) -> bool:
    root = root or ROOT
    data = _load_json(root / ".cursor/.session-ship-touched.json")
    touched = float(data.get("touched_at") or 0)
    if not touched:
        return False
    return (time.time() - touched) <= SESSION_MAX_AGE_SEC


def _recent_test_verified(root: Path) -> bool:
    q = _load_json(root / ".cursor/.ship-push-queue.json")
    passed_at = float(q.get("test_passed_at") or 0)
    if passed_at and (time.time() - passed_at) <= VERIFY_MAX_AGE_SEC:
        return q.get("status") == "verified"
    return False


def auto_close_mode(root: Path | None = None) -> str:
    """
    Decide whether workspace-autopilot end should run ship-loop close.

    Returns: none | workspace | full
    """
    root = root or ROOT
    if os.environ.get("WORKSPACE_AUTOPILOT_FORCE_CLOSE", "") == "1":
        return "full"

    sys_path = str(root / "scripts/lib")
    if sys_path not in __import__("sys").path:
        __import__("sys").path.insert(0, sys_path)
    try:
        from pending_ship_gc import gc_pending  # noqa: WPS433

        gc_pending(root)
    except Exception:
        pass

    pending_p = root / ".cursor/.pending-ship-work.json"
    passed_p = root / ".cursor/.ship-loop-passed.json"
    if not pending_p.is_file():
        return "none"

    from ship_push_gate import ship_loop_satisfied  # noqa: WPS433

    if ship_loop_satisfied(pending_p, passed_p):
        return "none"

    if not session_ship_active(root):
        return "none"

    pending = _load_json(pending_p)
    tier = pending.get("tier") or "workspace"
    state = _load_json(root / ".cursor/.autopilot-state.json")
    classification = state.get("last_classification") or ""

    if tier == "workspace":
        return "workspace"

    if _recent_test_verified(root):
        return "full"
    if classification in ("FIX+SHIP", "TEST", "FEATURE"):
        return "full"
    if os.environ.get("WORKSPACE_AUTOPILOT_CLOSE_ON_END", "") == "1":
        return "full"

    return "none"


def auto_close_reason(root: Path | None = None) -> str:
    root = root or ROOT
    mode = auto_close_mode(root)
    if mode != "none":
        return mode
    if not (root / ".cursor/.pending-ship-work.json").is_file():
        return "no pending"
    from ship_push_gate import ship_loop_satisfied  # noqa: WPS433

    if ship_loop_satisfied(root / ".cursor/.pending-ship-work.json", root / ".cursor/.ship-loop-passed.json"):
        return "already satisfied"
    if not session_ship_active(root):
        return "stale pending (no session ship touch)"
    return "analysis-only session — close when shipping"


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", action="store_true")
    ap.add_argument("--reason", action="store_true")
    ap.add_argument("--touch", action="store_true")
    ap.add_argument("--clear", action="store_true")
    ap.add_argument("--active", action="store_true")
    args = ap.parse_args()
    if args.touch:
        touch_session_ship()
        print("touched")
    elif args.clear:
        clear_session_ship()
        print("cleared")
    elif args.active:
        print("yes" if session_ship_active() else "no")
    elif args.reason:
        print(auto_close_reason())
    elif args.mode:
        print(auto_close_mode())
    else:
        ap.print_help()
