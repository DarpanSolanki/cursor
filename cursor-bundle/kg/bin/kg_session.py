#!/usr/bin/env python3
"""Fast multi-repo branch-set sync decisions — one git pass per repo.

Used by kg-session-sync.sh to avoid redundant kg fresh + doctor + kg-switch work.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import WORKSPACE, BUNDLE, KG_DATA, CHANGELOG, BRAIN  # noqa: E402
from kg_composite import composite_key, snapshot, repo_state, list_repos  # noqa: E402

KEY_FILE = WORKSPACE / ".cursor" / ".kg-composite-key"
BRANCH_SET_FILE = WORKSPACE / ".cursor" / ".kg-branch-set.json"
PENDING_FILE = WORKSPACE / ".cursor" / ".pending-kg-rebuild"
KG_DB = KG_DATA / "kg.db"
STATS = KG_DATA / "stats.json"
CACHE_DIR = KG_DATA / "cache"
RELEASE = re.compile(r"^mfi_(integration|release)_v[0-9]")


def _load_watermark() -> dict | None:
    try:
        return json.loads(STATS.read_text(encoding="utf-8")).get("watermark")
    except Exception:
        return None


def _changelog_kg_flow_newer_than_db() -> bool:
    if not CHANGELOG.is_file() or not KG_DB.is_file():
        return False
    try:
        if CHANGELOG.stat().st_mtime <= KG_DB.stat().st_mtime:
            return False
    except OSError:
        return False
    text = CHANGELOG.read_text(encoding="utf-8", errors="replace")[:8000]
    return bool(re.search(r"\bkg-flow\b|^KG-FLOW:", text, re.I | re.M))


def drift_lines() -> list[str]:
    """Repo drift vs kg.db watermark (branch / sha / uncommitted edits)."""
    wm = _load_watermark()
    if not wm:
        return ["no watermark — kg.db missing or never built"]
    drift: list[str] = []
    for repo, info in wm.get("repos", {}).items():
        live = repo_state(repo)
        lb, ls = live.get("branch"), (live.get("sha") or "")[:10]
        b, s = info.get("branch"), info.get("sha")
        if ls and s and ls != s:
            if lb != b:
                drift.append(f"{repo}: KG={b}@{s} → now {lb}@{ls}")
            else:
                drift.append(f"{repo}: KG@{s} → now @{ls} (same branch)")
            continue
        if live.get("dirty"):
            dh = live.get("dirty_hash") or ""
            if dh != (info.get("dirty_hash") or ""):
                drift.append(f"{repo}: @{ls} uncommitted edits not in KG")
        elif info.get("dirty"):
            drift.append(f"{repo}: KG built from dirty tree, now clean")
    return drift


def cache_hit_for_key(key: str) -> bool:
    db = CACHE_DIR / f"{key}.db"
    if not db.is_file():
        return False
    try:
        from kg_validate import validate_db  # type: ignore

        return validate_db(db) is True
    except Exception:
        return db.stat().st_size > 1024


def decide(*, fast: bool = False) -> dict:
    snap = snapshot()
    key = snap["key"]
    stored = KEY_FILE.read_text(encoding="utf-8").strip() if KEY_FILE.is_file() else ""
    pending = PENDING_FILE.is_file()
    drift = drift_lines()
    fresh = not drift
    key_changed = key != stored
    ch_cases = _changelog_kg_flow_newer_than_db()
    cached = cache_hit_for_key(key)

    tier = "skip"
    reason = "branch-set current"
    action = "none"

    if not KG_DB.is_file():
        tier, reason, action = "full", "kg.db missing", "kg-switch"
    elif drift:
        tier, reason, action = "full", "; ".join(drift[:3]), "kg-switch"
    elif ch_cases:
        tier, reason, action = "cases", "CHANGELOG kg-flow newer than kg.db", "refresh_cases"
    elif pending:
        tier, reason, action = "skip", "pending commit flag (audit-only until changelog)", "none"
    elif key_changed:
        if cached:
            tier, reason, action = "restore", f"branch-set key {key[:8]}… (cache hit)", "kg-switch"
        else:
            tier, reason, action = "full", f"new branch-set key {key[:8]}… (cache miss)", "kg-switch"

    # workspaceOpen fast path: skip all work when nothing changed
    if fast and fresh and tier == "skip" and not pending and key == stored:
        action = "none"

    wip = [r for r, v in snap["repos"].items() if v.get("provisional")]
    return {
        "key": key,
        "stored_key": stored,
        "fresh": fresh,
        "key_changed": key_changed,
        "cache_hit": cached,
        "pending": pending,
        "tier": tier,
        "reason": reason,
        "action": action,
        "wip_repos": len(wip),
        "repos": {
            r: {"branch": v["branch"], "sha": (v["sha"] or "")[:10], "dirty": v.get("dirty", False)}
            for r, v in snap["repos"].items()
        },
    }


def stamp() -> None:
    d = decide()
    KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    KEY_FILE.write_text(d["key"] + "\n", encoding="utf-8")
    BRANCH_SET_FILE.write_text(
        json.dumps(
            {
                "key": d["key"],
                "stamped_at": __import__("datetime").datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
                "repos": d["repos"],
                "wip_repos": d["wip_repos"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "decide"
    if cmd == "decide":
        fast = "--fast" in sys.argv
        print(json.dumps(decide(fast=fast), indent=2))
    elif cmd == "stamp":
        stamp()
        print(KEY_FILE.read_text(encoding="utf-8").strip())
    elif cmd == "key":
        print(composite_key())
    else:
        print("usage: kg_session.py [decide [--fast]|stamp|key]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
