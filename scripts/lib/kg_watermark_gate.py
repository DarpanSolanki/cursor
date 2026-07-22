#!/usr/bin/env python3
"""KG branch watermark gate — fail closed when live repos drift from kg.db watermark.

Used by workspace-autopilot end, workspace-close, and ship-loop to block verified claims
on stale branch@sha knowledge.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MONEY_REPOS = frozenset(
    {
        "trustt-platform-accounting",
        "trustt-platform-payments",
        "trustt-platform-los",
        "novopay-platform-accounting-v2",
        "novopay-platform-payments",
    }
)


def _kg_decide(root: Path) -> dict:
    script = root / "cursor-bundle/kg/bin/kg_session.py"
    r = subprocess.run(
        [sys.executable, str(script), "decide"],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=60,
    )
    if r.returncode != 0:
        return {"fresh": False, "tier": "unknown", "reason": (r.stderr or r.stdout or "decide failed")[:200]}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"fresh": False, "tier": "unknown", "reason": "invalid kg_session decide json"}


def drift_errors(root: Path, *, repos: frozenset[str] | None = None) -> list[str]:
    decide = _kg_decide(root)
    errors: list[str] = []
    if decide.get("fresh"):
        return errors
    reason = (decide.get("reason") or "branch/sha drift").strip()
    tier = decide.get("tier") or "full"
    errors.append(f"KG watermark stale (tier={tier}) — {reason}; run: scripts/bin/kg-switch.sh")
    if repos:
        live = decide.get("repos") or {}
        for repo in sorted(repos):
            if repo in live:
                info = live[repo]
                errors.append(
                    f"  live {repo}: {info.get('branch')}@{info.get('sha')}"
                )
    return errors


def accounting_mismatch(root: Path) -> list[str]:
    """Block when accounting HEAD branch@sha is not reflected in KG watermark."""
    acct = root / "trustt-platform-accounting"
    if not (acct / ".git").is_dir():
        return []
    r = subprocess.run(
        ["git", "-C", str(acct), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        return []
    live_branch = (r.stdout or "").strip()
    live_sha = subprocess.run(
        ["git", "-C", str(acct), "rev-parse", "--short=10", "HEAD"],
        capture_output=True,
        text=True,
    )
    live_sha_s = (live_sha.stdout or "").strip()
    stats = root / "cursor-bundle/kg/data/stats.json"
    if not stats.is_file():
        return [f"no kg stats.json — cannot verify accounting {live_branch}@{live_sha_s}"]
    try:
        wm = json.loads(stats.read_text(encoding="utf-8")).get("watermark") or {}
        info = (wm.get("repos") or {}).get("trustt-platform-accounting") or {}
        kb, ks = info.get("branch"), info.get("sha")
        if kb == live_branch and ks == live_sha_s:
            return []
        return [
            f"accounting branch mismatch: KG={kb}@{ks} live={live_branch}@{live_sha_s} "
            "— run scripts/bin/kg-switch.sh before verified claims"
        ]
    except (json.JSONDecodeError, OSError) as exc:
        return [f"watermark read error: {exc}"]


def check(*, root: Path | None = None, block_verified: bool = False, hard: bool = True) -> int:
    root = root or ROOT
    errors = drift_errors(root)
    if block_verified:
        errors.extend(accounting_mismatch(root))
    if errors:
        print("kg-watermark FAIL:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1 if hard else 0
    print("kg-watermark PASS: branch-set fresh")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="KG watermark gate")
    p.add_argument("cmd", nargs="?", default="check", choices=["check"])
    p.add_argument("--soft", action="store_true", help="Warn only (exit 0)")
    p.add_argument(
        "--block-verified",
        action="store_true",
        help="Also fail when trustt-platform-accounting != KG watermark",
    )
    p.add_argument("--root", default=str(ROOT))
    args = p.parse_args()
    return check(root=Path(args.root), block_verified=args.block_verified, hard=not args.soft)


if __name__ == "__main__":
    raise SystemExit(main())
