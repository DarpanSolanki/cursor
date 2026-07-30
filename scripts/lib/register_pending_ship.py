#!/usr/bin/env python3
"""Register or merge tiered pending ship work from paths or a git commit."""
from __future__ import annotations

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import (  # noqa: E402
    build_impact,
    classify_path,
    infer_repo_from_path,
    is_ship_path,
    merge_tier,
)
from ship_fingerprint import repo_head_shas  # noqa: E402

PENDING_DEFAULT = ROOT / ".cursor/.pending-ship-work.json"
LAST_COMMIT = ROOT / ".cursor/.last-ship-commit"


def _rel_path(root: Path, path: str) -> str:
    p = Path(path)
    if p.is_absolute():
        try:
            return str(p.relative_to(root))
        except ValueError:
            return path
    return path.replace("\\", "/")


def paths_from_commit(repo_dir: Path, ref: str = "HEAD") -> list[str]:
    if not (repo_dir / ".git").is_dir():
        return []
    out = subprocess.run(
        ["git", "-C", str(repo_dir), "diff-tree", "--no-commit-id", "--name-only", "-r", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        rel_repo = str(repo_dir.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        rel_repo = repo_dir.name
    prefix = "" if rel_repo in (".", "") else f"{rel_repo}/"
    paths: list[str] = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        full = f"{prefix}{line}"
        if is_ship_path(full):
            paths.append(full)
    return paths


def register_paths(
    root: Path,
    rel_paths: list[str],
    *,
    pending_path: Path | None = None,
    source: str = "edit",
) -> dict:
    """Merge ship paths into pending-ship-work.json; return summary."""
    pending_path = pending_path or (root / ".cursor/.pending-ship-work.json")
    pending_path.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    data: dict = {
        "tier": "workspace",
        "files": [],
        "apis": [],
        "repos": [],
        "registry_cases": [],
        "smoke_money_cases": [],
        "smoke_service_cases": [],
        "health_cases": [],
        "updated_at": now,
        "source": source,
    }
    if pending_path.is_file():
        try:
            data = json.loads(pending_path.read_text(encoding="utf-8"))
        except Exception:
            pass

    added = 0
    for raw in rel_paths:
        rel = _rel_path(root, raw)
        # Scratch is never ship-pending (pollutes sticky money close)
        if rel.replace("\\", "/").startswith("scripts/scratch/"):
            continue
        s = str(root / rel) if not rel.startswith("/") else rel
        if not is_ship_path(s):
            continue
        if rel not in data.setdefault("files", []):
            data["files"].append(rel)
            added += 1
        data["tier"] = merge_tier(data.get("tier"), classify_path(s))
        repo = infer_repo_from_path(s)
        if repo and repo not in data.setdefault("repos", []):
            data["repos"].append(repo)

    if not data.get("files"):
        return {"registered": False, "added": 0, "reason": "no ship paths"}

    all_paths = [str(root / x) if not x.startswith("/") else x for x in data["files"]]
    impact = build_impact(all_paths)
    data["tier"] = impact["tier"]
    data["apis"] = impact["apis"]
    rel_paths = list(data.get("files") or [])
    try:
        from impact_tests import build_plan  # noqa: WPS433

        plan = build_plan(from_pending=False, paths=rel_paths, shipped_only=True)
        ordered = list(plan.get("ordered_cases") or [])
        data["registry_cases"] = ordered or impact.get("ntest_cases") or impact.get("registry_cases") or []
        data["selection_source"] = "impact_tests" if ordered else "FALLBACK: no selection"
        data["resolution"] = data["selection_source"]
    except Exception:
        data["registry_cases"] = impact.get("ntest_cases") or impact.get("registry_cases") or []
        data["selection_source"] = "FALLBACK: no selection"
        data["resolution"] = "heuristic"
    data["ntest_cases"] = data["registry_cases"]
    data["smoke_money_cases"] = impact["smoke_money_cases"]
    data["smoke_service_cases"] = impact["smoke_service_cases"]
    data["health_cases"] = impact["health_cases"]
    pending_for_shas = {"repos": data.get("repos") or [], "files": data.get("files") or []}
    data["repo_head_shas"] = repo_head_shas(pending_for_shas)
    data["close_command"] = "bash scripts/bin/workspace-close.sh --from-pending"
    data["updated_at"] = now
    data.pop("ship_loop_passed_at", None)
    pending_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    nudge = root / ".cursor/.pending-ship-nudge"
    nudge.write_text((data["files"][-1] if data["files"] else "") + "\n", encoding="utf-8")

    return {
        "registered": True,
        "added": added,
        "tier": data["tier"],
        "apis": data["apis"],
        "ntest_cases": data["registry_cases"],
        "files": len(data["files"]),
    }


def register_from_last_commit(root: Path) -> dict:
    if not LAST_COMMIT.is_file():
        return {"registered": False, "reason": "no last-ship-commit"}
    lines = LAST_COMMIT.read_text(encoding="utf-8").splitlines()
    repo = lines[0].strip() if lines else ""
    if not repo:
        return {"registered": False, "reason": "empty last-ship-commit"}
    if repo in (".", ""):
        repo_dir = root
    else:
        repo_dir = root / repo
    if not (repo_dir / ".git").is_dir():
        return {"registered": False, "reason": f"not a git repo: {repo}"}
    paths = paths_from_commit(repo_dir, "HEAD")
    if not paths:
        return {"registered": False, "reason": "HEAD has no ship paths"}
    return register_paths(root, paths, source="commit")


def write_last_ship_commit(root: Path, repo_dir: Path, ref: str = "HEAD") -> Path:
    """Persist repo-relative name + sha for post-commit / ship-and-continue."""
    sha = subprocess.run(
        ["git", "-C", str(repo_dir), "rev-parse", ref],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    try:
        name = str(repo_dir.resolve().relative_to(root.resolve()))
    except ValueError:
        name = repo_dir.name
    if name == ".":
        name = "."
    LAST_COMMIT.parent.mkdir(parents=True, exist_ok=True)
    LAST_COMMIT.write_text(f"{name}\n{sha}\n", encoding="utf-8")
    return LAST_COMMIT


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[], help="Workspace-relative ship path")
    ap.add_argument("--from-commit", metavar="REPO", help="Service repo dir name under workspace")
    ap.add_argument("--ref", default="HEAD")
    ap.add_argument("--from-last-ship-commit", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    paths: list[str] = list(args.path)
    if args.from_commit:
        repo_dir = ROOT / args.from_commit
        if not (repo_dir / ".git").is_dir():
            for d in ROOT.iterdir():
                if d.is_dir() and args.from_commit in d.name and (d / ".git").is_dir():
                    repo_dir = d
                    break
        paths.extend(paths_from_commit(repo_dir, args.ref))

    if args.from_last_ship_commit:
        out = register_from_last_commit(ROOT)
    elif paths:
        out = register_paths(ROOT, paths, source="cli")
    else:
        ap.print_help()
        return 2

    if args.json:
        print(json.dumps(out, indent=2))
    elif out.get("registered"):
        print(
            f"pending ship: tier={out.get('tier')} files={out.get('files')} "
            f"cases={out.get('ntest_cases') or []}"
        )
    else:
        print(f"skip: {out.get('reason', 'nothing')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
