#!/usr/bin/env python3
"""Composite branch-set fingerprint for KG cache keys (all novopay-* / trustt-* repos).

Every caller of the KG state banner re-walked all 22 repos, so one `kg.py validate` spent 1.77s
of its 1.81s in 255 git subprocesses. The snapshot is memoised for a short window: a CLI process
lives well inside it, and a long-lived MCP server refreshes often enough that a branch switch
(which fires post-checkout + kg-switch anyway) is never served stale.
"""
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import WORKSPACE, BUNDLE, BRAIN, KG_DATA

RELEASE = re.compile(r"^mfi_(integration|release)_v[0-9]")

MEMO_TTL_S = float(os.environ.get("KG_COMPOSITE_MEMO_TTL_S", "3.0"))
_memo: dict[str, tuple[float, object]] = {}


def _cached(key: str, fn):
    hit = _memo.get(key)
    now = time.time()
    if hit and (now - hit[0]) < MEMO_TTL_S:
        return hit[1]
    val = fn()
    _memo[key] = (now, val)
    return val


def invalidate() -> None:
    _memo.clear()


def _git(d: Path, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(d), *args], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return ""


def list_repos() -> list[str]:
    def _scan() -> list[str]:
        repos = []
        for pat in ("novopay-*", "trustt-*"):
            for d in sorted(WORKSPACE.glob(pat)):
                if (d / ".git").is_dir():
                    repos.append(d.name)
        return repos

    return _cached("repos", _scan)


def _git_dir(d: Path) -> Path | None:
    g = d / ".git"
    if g.is_dir():
        return g
    if g.is_file():
        try:
            return (d / g.read_text(encoding="utf-8").split("gitdir:")[1].strip()).resolve()
        except Exception:
            return None
    return None


def _head_from_files(d: Path) -> tuple[str, str] | None:
    """Read branch + sha the way git itself does. Returns None so the caller falls back to git."""
    g = _git_dir(d)
    if g is None:
        return None
    try:
        head = (g / "HEAD").read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not head.startswith("ref: "):
        return ("HEAD", head) if re.fullmatch(r"[0-9a-f]{40}", head) else None
    ref = head[5:].strip()
    branch = ref.split("/", 2)[-1]
    loose = g / ref
    try:
        if loose.is_file():
            return branch, loose.read_text(encoding="utf-8").strip()
        packed = g / "packed-refs"
        if packed.is_file():
            for line in packed.read_text(encoding="utf-8").splitlines():
                if line.endswith(" " + ref):
                    return branch, line.split()[0]
    except Exception:
        return None
    return None


def _repo_state_uncached(repo: str) -> dict:
    d = WORKSPACE / repo
    head = _head_from_files(d)
    if head is not None:
        br, sha = head
    else:
        br = _git(d, "rev-parse", "--abbrev-ref", "HEAD") or "?"
        sha = _git(d, "rev-parse", "HEAD") or "?"
    porcelain = _git(d, "status", "--porcelain")
    dirty = bool(porcelain)
    rec = {"branch": br, "sha": sha, "dirty": dirty}
    if dirty:
        blob = porcelain + _git(d, "diff", "HEAD")
        rec["dirty_hash"] = hashlib.sha1(blob.encode("utf-8", "replace")).hexdigest()[:12]
        sha = f"{sha}+d{rec['dirty_hash']}"
    rec["cache_token"] = f"{repo}:{br}:{sha}"
    rec["provisional"] = bool(br and not RELEASE.match(br))
    return rec


def repo_state(repo: str) -> dict:
    return _cached(f"repo:{repo}", lambda: _repo_state_uncached(repo))


def prefetch_repo_states(repos: list[str] | None = None) -> None:
    """Warm every repo's state, serially and on purpose.

    This runs inside the MCP server's provenance header under a per-tool wall-clock cap. A
    ThreadPoolExecutor here re-creates the 2026-07-30 hang: `with` calls shutdown(wait=True) on a
    worker the server already abandoned, and its non-daemon threads block process exit. The memo
    plus reading branch/sha from git's own files is where the speed comes from — not concurrency.
    """
    for r in (repos or list_repos()):
        repo_state(r)


def docs_fingerprint() -> str:
    def _walk() -> str:
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

    return _cached("docs_fp", _walk)


def composite_string() -> str:
    def _build() -> str:
        repos = list_repos()
        prefetch_repo_states(repos)
        s = ""
        for r in repos:
            s += repo_state(r)["cache_token"] + "|"
        s += f"docs:{docs_fingerprint()}|"
        return s

    return _cached("composite", _build)


def composite_key() -> str:
    return _cached(
        "key",
        lambda: hashlib.sha1(composite_string().encode("utf-8", "replace")).hexdigest()[:16],
    )


def snapshot() -> dict:
    return {
        "composite": composite_string(),
        "key": composite_key(),
        "repos": {r: repo_state(r) for r in list_repos()},
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
