#!/usr/bin/env python3
"""Garbage-collect sticky .pending-ship-work.json — keep only unshipped work.

Standing failure: pending MERGEs forever across tasks; harness/docs push then
skips close but leaves zombie money paths → autopilot/ship-loop re-runs huge TAT.

Policy (fail-closed on uncertainty — keep path):
  DROP when path is scratch, missing, or **clean in its git repo and fully pushed**
  (no `origin/branch..HEAD` commits touching the path).
  KEEP when dirty or has unpushed commits touching the path.

Env:
  PENDING_SHIP_GC=0     disable GC
  PENDING_SHIP_GC_DRY=1 print actions only
"""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from ws_paths import norm_rel

ROOT = Path(__file__).resolve().parents[2]


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _norm(rel: str) -> str:
    return norm_rel(rel)


def _repo_and_rel(root: Path, rel: str) -> tuple[Path, str]:
    """Map workspace-relative path → (git_repo_dir, path_relative_to_that_repo)."""
    rel = _norm(rel)
    parts = rel.split("/")
    if parts and (parts[0].startswith("trustt-") or parts[0].startswith("novopay-")):
        repo = root / parts[0]
        if (repo / ".git").is_dir():
            return repo, "/".join(parts[1:]) if len(parts) > 1 else "."
    return root, rel


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def path_unshipped(root: Path, rel: str) -> tuple[bool, str]:
    """True → must stay in pending. False → safe to drop."""
    rel = _norm(rel)
    if not rel:
        return False, "empty"
    if rel.startswith("scripts/scratch/"):
        return False, "scratch"
    abs_p = root / rel
    if not abs_p.exists():
        return False, "missing"
    repo, repo_rel = _repo_and_rel(root, rel)
    if not (repo / ".git").is_dir():
        return True, "no-git-keep"

    st = _git(repo, "status", "--porcelain", "--", repo_rel)
    if (st.stdout or "").strip():
        return True, "dirty"

    # Upstream: origin/<branch> when tracking; else origin/HEAD tip name
    branch = (_git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout or "").strip()
    if not branch or branch == "HEAD":
        return True, "detached-keep"

    upstream = f"origin/{branch}"
    # Confirm upstream ref exists
    if _git(repo, "rev-parse", "--verify", upstream).returncode != 0:
        # No remote branch yet — committed locally only → still unshipped
        log_all = _git(repo, "log", "-1", "--oneline", "--", repo_rel)
        if (log_all.stdout or "").strip():
            return True, "no-upstream-keep"
        return False, "clean-untracked-history"

    unpushed = _git(repo, "log", f"{upstream}..HEAD", "--oneline", "--", repo_rel)
    if (unpushed.stdout or "").strip():
        return True, "unpushed"

    return False, "clean-and-pushed"


def rebuild_pending(root: Path, files: list[str], *, source: str = "gc") -> dict | None:
    """Rewrite pending from kept files, or None if empty (caller deletes)."""
    sys_path = str(root / "scripts/lib")
    import sys

    if sys_path not in sys.path:
        sys.path.insert(0, sys_path)
    from infer_ship_apis import build_impact, classify_path, infer_repo_from_path, merge_tier
    from ship_fingerprint import repo_head_shas

    kept = list(dict.fromkeys(_norm(f) for f in files if f))
    if not kept:
        return None
    now = _utc()
    abs_paths = [str(root / f) if not f.startswith("/") else f for f in kept]
    impact = build_impact(abs_paths)
    tier = "workspace"
    repos: list[str] = []
    for f in kept:
        tier = merge_tier(tier, classify_path(str(root / f)))
        r = infer_repo_from_path(f)
        if r and r not in repos:
            repos.append(r)
    try:
        from impact_tests import build_plan

        plan = build_plan(from_pending=False, paths=kept, shipped_only=True)
        cases = list(plan.get("ordered_cases") or []) or impact.get("ntest_cases") or []
        sel = "impact_tests" if plan.get("ordered_cases") else "FALLBACK"
    except Exception:
        cases = impact.get("ntest_cases") or impact.get("registry_cases") or []
        sel = "FALLBACK"
    data = {
        "tier": impact.get("tier") or tier,
        "files": kept,
        "apis": impact.get("apis") or [],
        "repos": impact.get("repos") or repos,
        "registry_cases": cases,
        "ntest_cases": cases,
        "smoke_money_cases": impact.get("smoke_money_cases") or [],
        "smoke_service_cases": impact.get("smoke_service_cases") or [],
        "health_cases": impact.get("health_cases") or [],
        "selection_source": sel,
        "resolution": sel,
        "repo_head_shas": repo_head_shas({"repos": repos, "files": kept}),
        "close_command": "bash scripts/bin/workspace-close.sh --from-pending",
        "updated_at": now,
        "source": source,
        "gc_at": now,
    }
    return data


def gc_pending(root: Path | None = None, *, dry_run: bool | None = None) -> dict:
    """GC pending ship work. Returns summary dict."""
    root = root or ROOT
    if os.environ.get("PENDING_SHIP_GC", "1").strip() in ("0", "false", "no", "off"):
        return {"enabled": False, "kept": [], "dropped": []}
    if dry_run is None:
        dry_run = os.environ.get("PENDING_SHIP_GC_DRY", "").strip() in ("1", "true", "yes")

    pending_path = root / ".cursor" / ".pending-ship-work.json"
    pending = _load(pending_path)
    files = list(pending.get("files") or [])
    if not files:
        return {"enabled": True, "empty": True, "kept": [], "dropped": []}

    kept: list[str] = []
    dropped: list[dict] = []
    for f in files:
        unshipped, reason = path_unshipped(root, f)
        if unshipped:
            kept.append(_norm(f))
        else:
            dropped.append({"file": _norm(f), "reason": reason})

    summary = {
        "enabled": True,
        "dry_run": dry_run,
        "before": len(files),
        "kept": kept,
        "dropped": dropped,
        "after": len(kept),
    }
    if dry_run or kept == [_norm(f) for f in files]:
        return summary

    nudge = root / ".cursor" / ".pending-ship-nudge"
    if not kept:
        pending_path.unlink(missing_ok=True)
        nudge.unlink(missing_ok=True)
        summary["cleared"] = True
        return summary

    data = rebuild_pending(root, kept, source=f"gc:{pending.get('source') or 'edit'}")
    if not data:
        pending_path.unlink(missing_ok=True)
        nudge.unlink(missing_ok=True)
        summary["cleared"] = True
        return summary
    # Preserve updated_at bump only when we dropped — ship_loop fingerprint gate
    pending_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    summary["tier"] = data.get("tier")
    return summary


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    summary = gc_pending(Path(args.root), dry_run=args.dry_run)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(
            f"pending-ship-gc: before={summary.get('before', 0)} "
            f"after={summary.get('after', len(summary.get('kept') or []))} "
            f"dropped={len(summary.get('dropped') or [])}"
            + (" DRY" if summary.get("dry_run") else "")
            + (" CLEARED" if summary.get("cleared") else "")
        )
        for d in summary.get("dropped") or []:
            print(f"  DROP {d.get('file')} ({d.get('reason')})")
        for k in summary.get("kept") or []:
            print(f"  KEEP {k}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
