#!/usr/bin/env python3
"""Shared ship-loop vs push gate checks (pre-push hook, push-origin.sh)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER_RANK = {"workspace": 0, "service": 1, "money": 2}


def file_fingerprint(root: Path, rel_path: str) -> str:
    p = Path(rel_path)
    if not p.is_absolute():
        p = root / rel_path
    if not p.is_file():
        return ""
    st = p.stat()
    return f"{st.st_size}:{int(st.st_mtime)}"


def fingerprints_for_files(root: Path, files: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for rel in files or []:
        key = rel.replace("\\", "/")
        fp = file_fingerprint(root, key)
        if fp:
            out[key] = fp
    return out


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def pending_needs_ship_loop(pending_path: Path, passed_path: Path) -> bool:
    pending = load_json(pending_path)
    files = pending.get("files") or []
    apis = pending.get("apis") or []
    if not files and not apis:
        return False
    return not ship_loop_satisfied(pending_path, passed_path)


def ship_loop_satisfied(pending_path: Path, passed_path: Path) -> bool:
    pending = load_json(pending_path)
    files = pending.get("files") or []
    apis = set(pending.get("apis") or [])
    if not files and not apis:
        return True
    passed = load_json(passed_path)
    if not passed:
        return False
    updated = pending.get("updated_at", "")
    if (passed.get("passed_at") or "") < updated:
        return False
    ptier = passed.get("tier") or "workspace"
    tier = pending.get("tier") or "workspace"
    if TIER_RANK.get(ptier, 0) < TIER_RANK.get(tier, 0):
        return False
    if apis and not apis.issubset(set(passed.get("apis") or [])):
        return False
    # Fingerprint gate: files changed since the last PASS must re-run ship-loop
    root = pending_path.parent.parent if pending_path.parent.name == ".cursor" else ROOT
    current = fingerprints_for_files(root, files)
    passed_fps = passed.get("file_fingerprints") or {}
    if passed_fps:
        for rel in files:
            key = rel.replace("\\", "/")
            cur = current.get(key)
            if cur and passed_fps.get(key) and cur != passed_fps.get(key):
                return False
    return True


def should_skip_auto_close_for_knowledge_head(repo_dir: Path | None = None) -> bool:
    """Skip money/DPIC ship-loop when HEAD has no service-repo product code.

    Covers:
      - knowledge/docs/KG gate scripts (legacy)
      - workspace harness-only HEAD (disburse_* / neft_v2 / scripts/testing / .gitignore)

    Sticky money that is already clean+pushed is GC'd (pending_ship_gc). Only
    dirty/unpushed service paths remain — and they must NOT force a money
    ship-loop on a harness/docs push.
    """
    repo = repo_dir or ROOT
    if not (is_knowledge_only_head(repo) or is_workspace_push_safe_head(repo)):
        return False
    try:
        _prune_non_service_paths_from_pending()
    except Exception:
        pass
    try:
        sys.path.insert(0, str(ROOT / "scripts/lib"))
        from pending_ship_gc import gc_pending  # noqa: WPS433

        gc_pending(ROOT)
    except Exception:
        pass
    return True


def is_workspace_push_safe_head(repo_dir: Path | None = None) -> bool:
    """HEAD touches zero service repos — safe to push without sticky money close."""
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import head_commit_paths  # noqa: WPS433
    from ship_change_scope import is_workspace_push_safe_paths  # noqa: WPS433

    return is_workspace_push_safe_paths(head_commit_paths(repo_dir or ROOT))


def _prune_non_service_paths_from_pending() -> None:
    """Drop knowledge/harness/scratch/kb from pending; keep service money for later."""
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import build_impact, is_knowledge_path, is_service_path, infer_repo_from_path  # noqa: WPS433
    from ship_change_scope import is_scratch_path, partition_ship_paths  # noqa: WPS433

    pending_path = ROOT / ".cursor/.pending-ship-work.json"
    pending = load_json(pending_path)
    files = list(pending.get("files") or [])
    if not files:
        return

    kept: list[str] = []
    for f in files:
        s = str(f)
        if is_scratch_path(s) or is_knowledge_path(s):
            continue
        parts = partition_ship_paths([s])
        if parts["service"] or is_service_path(s) or infer_repo_from_path(s):
            kept.append(s)
            continue
        # harness / testing_infra / workspace kb — drop from sticky pending on safe push
        continue

    if kept == files:
        return
    if not kept:
        pending_path.unlink(missing_ok=True)
        return
    pending["files"] = kept
    abs_paths = [
        str(ROOT / x) if not str(x).startswith("/") else str(x) for x in kept
    ]
    impact = build_impact(abs_paths)
    pending["tier"] = impact.get("tier") or pending.get("tier") or "workspace"
    pending["apis"] = impact.get("apis") or []
    pending["repos"] = impact.get("repos") or pending.get("repos") or []
    pending["registry_cases"] = impact.get("ntest_cases") or impact.get("registry_cases") or []
    pending["ntest_cases"] = pending["registry_cases"]
    pending_path.write_text(json.dumps(pending, indent=2) + "\n", encoding="utf-8")


def pending_apis(pending_path: Path) -> list[str]:
    pending = load_json(pending_path)
    apis = list(pending.get("apis") or [])
    if apis:
        return apis
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import infer_from_path  # noqa: WPS433

    root = ROOT
    for rel in pending.get("files") or []:
        p = str(root / rel) if not str(rel).startswith("/") else str(rel)
        api = infer_from_path(p)
        if api and api not in apis:
            apis.append(api)
    return apis


def is_merge_commit(repo_dir: Path) -> bool:
    if not (repo_dir / ".git").is_dir():
        return False
    if subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", "--verify", "HEAD^2"],
        capture_output=True,
        check=False,
    ).returncode == 0:
        return True
    subj = subprocess.run(
        ["git", "-C", str(repo_dir), "log", "-1", "--format=%s"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    return subj.startswith("Merge ")


def is_knowledge_only_head(repo_dir: Path | None = None) -> bool:
    """HEAD only touches .cursor/cursor-bundle/docs — do not block push on money pending."""
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import is_knowledge_only_head as _ikoh  # noqa: WPS433

    return _ikoh(repo_dir or ROOT)


def last_ship_repo_dir() -> Path | None:
    last = ROOT / ".cursor/.last-ship-commit"
    if not last.is_file():
        return None
    lines = last.read_text(encoding="utf-8").splitlines()
    repo = lines[0].strip() if lines else ""
    if not repo:
        return None
    candidate = ROOT / repo
    return candidate if (candidate / ".git").is_dir() else None


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--needs-close", action="store_true")
    ap.add_argument("--satisfied", action="store_true")
    ap.add_argument("--pending-apis", action="store_true")
    ap.add_argument("--is-merge-head", action="store_true")
    ap.add_argument("--is-knowledge-head", action="store_true")
    ap.add_argument("--is-workspace-safe-head", action="store_true")
    ap.add_argument("--skip-auto-close-knowledge", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()
    root = Path(args.root)
    pending_p = root / ".cursor/.pending-ship-work.json"
    passed_p = root / ".cursor/.ship-loop-passed.json"

    if args.needs_close:
        sys.exit(0 if pending_needs_ship_loop(pending_p, passed_p) else 1)
    if args.satisfied:
        sys.exit(0 if ship_loop_satisfied(pending_p, passed_p) else 1)
    if args.pending_apis:
        for api in pending_apis(pending_p):
            print(api)
        return 0
    if args.skip_auto_close_knowledge:
        sys.exit(0 if should_skip_auto_close_for_knowledge_head(root) else 1)
    if args.is_knowledge_head:
        sys.exit(0 if is_knowledge_only_head(root) else 1)
    if args.is_workspace_safe_head:
        sys.exit(0 if is_workspace_push_safe_head(root) else 1)
    if args.is_merge_head:
        repo = last_ship_repo_dir()
        if repo and is_merge_commit(repo):
            sys.exit(0)
        # fallback: any dirty service repo HEAD
        for d in sorted(root.iterdir()):
            if d.is_dir() and d.name.startswith(("novopay-", "trustt-")) and (d / ".git").is_dir():
                if is_merge_commit(d):
                    sys.exit(0)
        sys.exit(1)
    ap.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
