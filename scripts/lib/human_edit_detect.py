#!/usr/bin/env python3
"""Human-edit detector — fingerprint dirty trees at session close; warn on next sessionStart.

Read-only / warn-only. Never blocks. ~fingerprint of (repo, path, mtime, size, sha1-short).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FP_PATH = ROOT / ".cursor" / ".session-close-fingerprint.json"
WARN_PATH = ROOT / ".cursor" / ".human-edit-warn.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _repos() -> list[Path]:
    out = []
    for p in sorted(ROOT.iterdir()):
        if p.is_dir() and (p / ".git").exists() and (
            p.name.startswith("trustt-") or p.name.startswith("novopay-")
        ):
            out.append(p)
    # workspace root itself (harness)
    if (ROOT / ".git").exists():
        out.append(ROOT)
    return out


def _dirty_entries(repo: Path) -> list[dict]:
    r = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=False,
    )
    entries = []
    for line in (r.stdout or "").splitlines():
        if len(line) < 4:
            continue
        # XY PATH or XY ORIG -> PATH
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path.startswith('"') and path.endswith('"'):
            path = path[1:-1]
        full = repo / path if repo != ROOT else ROOT / path
        # For workspace root, skip service subrepos' nested noise already covered
        if repo == ROOT and (
            path.startswith("trustt-") or path.startswith("novopay-")
        ):
            continue
        st = full.stat() if full.is_file() else None
        digest = ""
        if st and st.st_size <= 2_000_000 and full.is_file():
            try:
                digest = hashlib.sha1(full.read_bytes()).hexdigest()[:12]
            except OSError:
                digest = ""
        rel = str(full.relative_to(ROOT)) if full.exists() else f"{repo.name}/{path}"
        entries.append(
            {
                "repo": repo.name if repo != ROOT else "sliProd",
                "path": rel,
                "mtime": int(st.st_mtime) if st else 0,
                "size": int(st.st_size) if st else 0,
                "sha1_12": digest,
                "git_xy": line[:2],
            }
        )
    return entries


def write_fingerprint(*, actor: str = "session-close") -> dict:
    files: list[dict] = []
    for repo in _repos():
        files.extend(_dirty_entries(repo))
    files.sort(key=lambda e: e["path"])
    payload = {
        "written_at": _utc(),
        "actor": actor,
        "file_count": len(files),
        "files": files,
    }
    FP_PATH.parent.mkdir(parents=True, exist_ok=True)
    FP_PATH.write_text(json.dumps(payload, indent=2) + "\n")
    return payload


def session_start() -> int:
    """Load prior fingerprint, compare to live dirty, then refresh fingerprint stamp optional.

    Does NOT overwrite prior until after diff — read prior first.
    """
    prior = None
    if FP_PATH.is_file():
        prior = json.loads(FP_PATH.read_text())
    live = []
    for repo in _repos():
        live.extend(_dirty_entries(repo))
    live_map = {e["path"]: e for e in live}
    prev_map = {e["path"]: e for e in (prior or {}).get("files") or []}

    added, changed = [], []
    for path, e in live_map.items():
        if path not in prev_map:
            added.append(e)
        else:
            o = prev_map[path]
            if e.get("mtime") != o.get("mtime") or e.get("size") != o.get("size") or (
                e.get("sha1_12") and e.get("sha1_12") != o.get("sha1_12")
            ):
                changed.append(e)

    suggest: list[str] = []
    moneyish = [
        a["path"]
        for a in (added + changed)
        if any(tok in a["path"] for tok in ("accounting", ".java", "orch", "flowtest"))
    ]
    if moneyish and (added or changed):
        try:
            sys.path.insert(0, str(ROOT / "scripts/lib"))
            from impact_tests import build_plan  # type: ignore

            plan = build_plan(paths=moneyish[:20], from_pending=False, shipped_only=False)
            suggest = list(plan.get("ntest_cases") or [])[:12]
        except Exception as exc:  # noqa: BLE001
            suggest = [f"(impact_tests unavailable: {exc})"]

    warn = bool(prior and (added or changed))
    out = {
        "warn": warn,
        "checked_at": _utc(),
        "prior_written_at": (prior or {}).get("written_at"),
        "added": [{"path": a["path"], "repo": a.get("repo")} for a in added[:40]],
        "changed": [{"path": c["path"], "repo": c.get("repo")} for c in changed[:40]],
        "suggested_cases": suggest,
    }
    WARN_PATH.write_text(json.dumps(out, indent=2) + "\n")
    if warn:
        print("HUMAN-EDIT WARN: dirty tree drifted since last session close")
        for a in out["added"][:15]:
            print(f"  + {a['path']}")
        for c in out["changed"][:15]:
            print(f"  ~ {c['path']}")
        if suggest:
            print("  suggested cases:", ", ".join(suggest[:8]))
        print(f"  detail: {WARN_PATH}")
    else:
        print("HUMAN-EDIT OK: no new dirty drift vs last close fingerprint")
    # Do not overwrite close fingerprint on start — only stamp if missing
    if not prior:
        write_fingerprint(actor="session-start-init")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print("usage: human_edit_detect.py {close|start|status}")
        return 2
    cmd = argv[1]
    if cmd == "close":
        p = write_fingerprint(actor="session-close")
        print(f"HUMAN-EDIT fingerprint written files={p['file_count']} → {FP_PATH}")
        return 0
    if cmd == "start":
        return session_start()
    if cmd == "status":
        if WARN_PATH.is_file():
            print(WARN_PATH.read_text())
        elif FP_PATH.is_file():
            print(f"fingerprint only: {FP_PATH}")
        else:
            print("no fingerprint/warn yet")
        return 0
    print("unknown command", cmd)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
