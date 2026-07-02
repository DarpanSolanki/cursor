#!/usr/bin/env python3
"""Composite branch-set fingerprint for KG cache keys (all novopay-* / trustt-* repos)."""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import WORKSPACE, BUNDLE, BRAIN, KG_DATA

RELEASE = re.compile(r"^mfi_(integration|release)_v[0-9]")


def _git(d: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(d), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def list_repos() -> list[str]:
    repos = []
    for pat in ("novopay-*", "trustt-*"):
        for d in sorted(WORKSPACE.glob(pat)):
            if (d / ".git").is_dir():
                repos.append(d.name)
    return repos


def repo_state(repo: str) -> dict:
    d = WORKSPACE / repo
    br = _git(d, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    sha = _git(d, "rev-parse", "HEAD") or "?"
    dirty = bool(_git(d, "status", "--porcelain"))
    rec = {"branch": br, "sha": sha, "dirty": dirty}
    if dirty:
        blob = _git(d, "status", "--porcelain") + _git(d, "diff", "HEAD")
        rec["dirty_hash"] = hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()[:12]
        sha = f"{sha}+d{rec['dirty_hash']}"
    rec["cache_token"] = f"{repo}:{br}:{sha}"
    rec["provisional"] = bool(br and not RELEASE.match(br))
    return rec


def docs_fingerprint() -> str:
    parts = []
    for base, prefix in ((BRAIN, ""), (BUNDLE / "kg" / "curated", "cur/")):
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in (".md", ".jsonl"):
                rel = prefix + str(p.relative_to(base))
                parts.append(f"{rel} {p.stat().st_mtime_ns} {p.stat().st_size}")
    blob = "\n".join(parts).encode("utf-8", "replace")
    return hashlib.sha1(blob).hexdigest()[:12]


def composite_string() -> str:
    s = ""
    for r in list_repos():
        s += repo_state(r)["cache_token"] + "|"
    s += f"docs:{docs_fingerprint()}|"
    return s


def composite_key() -> str:
    return hashlib.sha1(composite_string().encode("utf-8", "replace")).hexdigest()[:16]


def snapshot() -> dict:
    repos = {}
    for r in list_repos():
        repos[r] = repo_state(r)
    return {
        "composite": composite_string(),
        "key": composite_key(),
        "repos": repos,
        "docs_fp": docs_fingerprint(),
    }


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "key"
    if cmd == "key":
        print(composite_key())
    elif cmd == "composite":
        print(composite_string())
    elif cmd == "snapshot":
        print(json.dumps(snapshot(), indent=2))
    elif cmd == "repos":
        print("\n".join(list_repos()))
    else:
        print("usage: kg_composite.py [key|composite|snapshot|repos]", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
