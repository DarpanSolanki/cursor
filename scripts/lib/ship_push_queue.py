#!/usr/bin/env python3
"""Push queue + repo ahead detection for ship-and-continue autopilot."""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUEUE_PATH = ROOT / ".cursor/.ship-push-queue.json"
LAST_SHIP = ROOT / ".cursor/.last-ship-commit"
PENDING = ROOT / ".cursor/.pending-ship-work.json"

DEFAULT_COOLDOWN_SEC = int(os.environ.get("SHIP_PUSH_COOLDOWN_SEC", "20"))
QUEUE_MAX_AGE_SEC = int(os.environ.get("SHIP_PUSH_QUEUE_MAX_AGE_SEC", "7200"))


def load_queue() -> dict:
    if not QUEUE_PATH.is_file():
        return {}
    try:
        data = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}
    passed_at = float(data.get("test_passed_at") or 0)
    if passed_at and (time.time() - passed_at) > QUEUE_MAX_AGE_SEC:
        clear_queue()
        return {}
    return data


def save_queue(data: dict) -> None:
    QUEUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    QUEUE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def clear_queue() -> None:
    if QUEUE_PATH.is_file():
        QUEUE_PATH.unlink()


def resolve_repo_name(name: str) -> str | None:
    """Resolve short alias to service repo dir name."""
    if not name:
        return None
    if (ROOT / name / ".git").is_dir():
        return name
    for d in sorted(ROOT.iterdir()):
        if not d.is_dir() or not (d / ".git").is_dir():
            continue
        base = d.name
        if not base.startswith(("novopay-", "trustt-")):
            continue
        if base == name or name in base:
            return base
    return None


def infer_ship_repo() -> str | None:
    if LAST_SHIP.is_file():
        repo = LAST_SHIP.read_text(encoding="utf-8").splitlines()[0].strip()
        resolved = resolve_repo_name(repo)
        if resolved:
            return resolved
    if PENDING.is_file():
        try:
            pending = json.loads(PENDING.read_text(encoding="utf-8"))
            for rel in pending.get("files") or []:
                parts = Path(rel).parts
                if parts and parts[0].startswith(("novopay-", "trustt-")):
                    return parts[0]
        except Exception:
            pass
    return None


def git(repo: str, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(ROOT / repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def repo_dirty(repo: str) -> bool:
    r = git(repo, "status", "--porcelain")
    return bool(r.stdout.strip())


def commits_ahead_of_origin(repo: str) -> int:
    if not (ROOT / repo / ".git").is_dir():
        return 0
    branch = git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if not branch or branch == "HEAD":
        return 0
    upstream = git(repo, "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}").stdout.strip()
    if upstream and "fatal" not in upstream.lower():
        spec = f"{upstream}..HEAD"
    elif git(repo, "rev-parse", "--verify", f"origin/{branch}").returncode == 0:
        spec = f"origin/{branch}..HEAD"
    else:
        return 0
    r = git(repo, "rev-list", "--count", spec)
    try:
        n = int((r.stdout or "0").strip())
        return n if n >= 0 else 0
    except ValueError:
        return 0


def mark_test_passed(api: str = "", repo: str | None = None) -> dict:
    repo_raw = repo or infer_ship_repo() or ""
    resolved = resolve_repo_name(repo_raw) if repo_raw else infer_ship_repo()
    now = time.time()
    data = {
        "api": api,
        "repo": resolved or repo_raw,
        "test_passed_at": now,
        "ready_after": now + DEFAULT_COOLDOWN_SEC,
        "cooldown_sec": DEFAULT_COOLDOWN_SEC,
        "status": "verified",
    }
    save_queue(data)
    return data


def queue_ready(force: bool = False) -> tuple[bool, str]:
    q = load_queue()
    if not q or q.get("status") != "verified":
        return False, "no verified test in queue"
    if not force and time.time() < float(q.get("ready_after") or 0):
        wait = int(float(q["ready_after"]) - time.time())
        return False, f"cooldown {wait}s remaining"
    repo_raw = q.get("repo") or infer_ship_repo()
    repo = resolve_repo_name(repo_raw or "") if repo_raw else infer_ship_repo()
    if not repo:
        return False, "cannot infer ship repo"
    if not (ROOT / repo / ".git").is_dir():
        return False, f"unknown repo: {repo}"
    if repo_dirty(repo):
        return False, f"{repo} has uncommitted changes — commit first"
    ahead = commits_ahead_of_origin(repo)
    if ahead == 0:
        return False, f"{repo} nothing to push (0 commits ahead)"
    return True, repo


def mark_pushed(repo: str) -> None:
    clear_queue()
    state = ROOT / ".cursor/.autopilot-state.json"
    data: dict = {}
    if state.is_file():
        try:
            data = json.loads(state.read_text(encoding="utf-8"))
        except Exception:
            pass
    data["last_push_at"] = time.time()
    data["last_push_repo"] = repo
    state.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def self_check() -> list[dict]:
    """Dry checks for verify — no network push."""
    checks: list[dict] = []
    repo = infer_ship_repo()
    checks.append({"id": "infer_repo", "ok": True, "detail": repo or "(none — ok if no pending ship)"})
    q = load_queue()
    checks.append({"id": "queue_parse", "ok": True, "detail": "empty" if not q else q.get("status")})
    alias = resolve_repo_name("accounting-v2")
    checks.append({
        "id": "repo_alias",
        "ok": alias is None or (ROOT / alias / ".git").is_dir(),
        "detail": alias or "no accounting-v2 alias",
    })
    if repo:
        checks.append({
            "id": "commits_ahead",
            "ok": True,
            "detail": str(commits_ahead_of_origin(repo)),
        })
    return checks
