#!/usr/bin/env python3
"""Deterministic ship fingerprints — commit SHA keyed; knowledge paths exempt (single SoT)."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Permanent exempt class — never hash working-tree knowledge/bookkeeping (contract §1).
FINGERPRINT_EXEMPT_PREFIXES: tuple[str, ...] = (
    ".cursor/",
    "cursor-bundle/brain/changelog/",
    "cursor-bundle/memory/SELF-REPORT.md",
    "cursor-bundle/kg/curated/promoted_learnings.jsonl",
    "scripts/testing/registry-proposals.json",
    "scripts/scratch/",
    "system_brain/",
    "docs/",
)

FINGERPRINT_EXEMPT_EXACT: frozenset[str] = frozenset(
    {
        ".cursor/changelog.md",
        "cursor-bundle/memory/SELF-REPORT.md",
        "scripts/testing/registry-proposals.json",
    }
)

TRAIN_RE = re.compile(r"^mfi_(?:integration|release)_v(?P<version>\d+(?:\.\d+)*)$")


def _norm_rel(rel_path: str) -> str:
    s = rel_path.replace("\\", "/")
    if s.startswith("./"):
        return s[2:]
    return s


def is_fingerprint_exempt(rel_path: str) -> bool:
    """True when path must never participate in ship gate fingerprints."""
    s = _norm_rel(rel_path)
    if s in FINGERPRINT_EXEMPT_EXACT:
        return True
    return any(s.startswith(p) for p in FINGERPRINT_EXEMPT_PREFIXES)


def repo_of(rel: str) -> str:
    s = rel.replace("\\", "/")
    if s.startswith("trustt-") or s.startswith("novopay-"):
        return s.split("/", 1)[0]
    return ""


def repo_head_sha(repo_path: Path) -> str:
    if not (repo_path / ".git").is_dir():
        return ""
    r = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_branch(repo_path: Path) -> str:
    if not (repo_path / ".git").is_dir():
        return ""
    r = subprocess.run(
        ["git", "-C", str(repo_path), "branch", "--show-current"],
        capture_output=True,
        text=True,
        check=False,
    )
    return r.stdout.strip() if r.returncode == 0 else ""


def repo_train_version(repo_path: Path) -> str | None:
    branch = repo_branch(repo_path)
    m = TRAIN_RE.match(branch)
    return m.group("version") if m else None


def upstream_ref(repo_path: Path) -> str | None:
    if not (repo_path / ".git").is_dir():
        return None
    r = subprocess.run(
        ["git", "-C", str(repo_path), "rev-parse", "--abbrev-ref", "@{upstream}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return None
    return r.stdout.strip()


def ship_range_paths(repo_path: Path, repo_name: str) -> list[str]:
    """Non-exempt paths in upstream...HEAD (shipped code only)."""
    if not (repo_path / ".git").is_dir():
        return []
    up = upstream_ref(repo_path)
    if up:
        cmd = ["git", "-C", str(repo_path), "diff", "--name-only", f"{up}...HEAD"]
    else:
        cmd = ["git", "-C", str(repo_path), "diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD"]
    r = subprocess.run(cmd, capture_output=True, text=True, check=False)
    prefix = "" if repo_name in (".", "") else f"{repo_name}/"
    out: list[str] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        rel = f"{prefix}{line}" if prefix else line
        if not is_fingerprint_exempt(rel):
            out.append(rel.replace("\\", "/"))
    return sorted(set(out))


def primary_ship_repos(pending: dict | None) -> list[tuple[str, Path]]:
    """Ordered (repo_name, repo_path) for service repos in pending ship work."""
    pending = pending or {}
    seen: set[str] = set()
    out: list[tuple[str, Path]] = []
    for repo in pending.get("repos") or []:
        if repo in seen:
            continue
        p = ROOT / repo
        if (p / ".git").is_dir() and repo.startswith(("trustt-", "novopay-")):
            seen.add(repo)
            out.append((repo, p))
    if out:
        return out
    for rel in pending.get("files") or []:
        repo = repo_of(str(rel))
        if repo and repo not in seen:
            p = ROOT / repo
            if (p / ".git").is_dir():
                seen.add(repo)
                out.append((repo, p))
    return out


def repo_head_shas(pending: dict | None) -> dict[str, str]:
    return {name: repo_head_sha(path) for name, path in primary_ship_repos(pending)}


def load_pending(path: Path | None = None) -> dict:
    p = path or (ROOT / ".cursor/.pending-ship-work.json")
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def human_waiver_active() -> tuple[bool, str]:
    """Explicit human waiver file only — no env escape hatch."""
    wp = ROOT / ".cursor/.impact-tests-human-waiver.json"
    if not wp.is_file():
        return False, ""
    try:
        data = json.loads(wp.read_text(encoding="utf-8"))
    except Exception:
        return False, "corrupt human waiver file"
    reason = str(data.get("reason") or "").strip()
    actor = str(data.get("actor") or "human").strip()
    if not reason:
        return False, "human waiver missing reason"
    return True, f"human waiver actor={actor} reason={reason}"
