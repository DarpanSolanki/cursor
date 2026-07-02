#!/usr/bin/env python3
"""Multi-repo git workspace status — upstream/origin aware, cross-session state.

State files (persist across agent sessions):
  .cursor/git-workspace-state.json   — last scan (all repos, drift vs origin/upstream)
  .cursor/git-branch-manifest.json   — per-repo branch overrides (feature work on one service)

Usage:
  git_workspace.py status [--write] [--json]
  git_workspace.py manifest
  git_workspace.py set-override <repo> <branch>
  git_workspace.py clear-override <repo>
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURSOR = ROOT / ".cursor"
STATE_FILE = CURSOR / "git-workspace-state.json"
MANIFEST_FILE = CURSOR / "git-branch-manifest.json"
UPSTREAM_ORG = "khoslalabs"
INTEGRATION = re.compile(r"^mfi_(integration|release)_v[0-9]")


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
        for d in sorted(ROOT.glob(pat)):
            if (d / ".git").is_dir():
                repos.append(d.name)
    return repos


def load_manifest() -> dict:
    if MANIFEST_FILE.is_file():
        try:
            return json.loads(MANIFEST_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"default_branch": "", "overrides": {}, "notes": "Per-repo branch overrides for multi-branch workspace sync."}


def save_manifest(m: dict) -> None:
    CURSOR.mkdir(parents=True, exist_ok=True)
    MANIFEST_FILE.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


def _count(ref: str, d: Path) -> int | None:
    if not ref:
        return None
    c = _git(d, "rev-list", "--count", f"HEAD..{ref}")
    try:
        return int(c)
    except ValueError:
        return None


def _behind(ref: str, d: Path) -> int | None:
    if not ref:
        return None
    c = _git(d, "rev-list", "--count", f"{ref}..HEAD")
    try:
        return int(c)
    except ValueError:
        return None


def repo_status(name: str) -> dict:
    d = ROOT / name
    br = _git(d, "rev-parse", "--abbrev-ref", "HEAD") or "?"
    sha = _git(d, "rev-parse", "--short=10", "HEAD") or "?"
    dirty = bool(_git(d, "status", "--porcelain"))
    origin_url = _git(d, "remote", "get-url", "origin") if _git(d, "remote") and "origin" in _git(d, "remote") else ""
    has_upstream = "upstream" in (_git(d, "remote") or "")
    upstream_br = ""
    origin_br = ""
    if has_upstream and _git(d, "rev-parse", "--verify", f"refs/remotes/upstream/{br}"):
        upstream_br = f"upstream/{br}"
    if _git(d, "rev-parse", "--verify", f"refs/remotes/origin/{br}"):
        origin_br = f"origin/{br}"

    rec = {
        "branch": br,
        "sha": sha,
        "dirty": dirty,
        "provisional": bool(br and not INTEGRATION.match(br)),
        "origin_url": origin_url,
        "has_upstream": has_upstream,
        "origin_behind": _count(origin_br, d) if origin_br else None,
        "origin_ahead": _behind(origin_br, d) if origin_br else None,
        "upstream_behind": _count(upstream_br, d) if upstream_br else None,
        "upstream_ahead": _behind(upstream_br, d) if upstream_br else None,
    }
    return rec


def collect_status() -> dict:
    manifest = load_manifest()
    repos = {}
    dirty_n = prov_n = upstream_behind_n = 0
    for r in list_repos():
        rs = repo_status(r)
        repos[r] = rs
        if rs["dirty"]:
            dirty_n += 1
        if rs["provisional"]:
            prov_n += 1
        ub = rs.get("upstream_behind")
        if ub is not None and ub > 0:
            upstream_behind_n += 1

    kg_key = ""
    try:
        sys.path.insert(0, str(ROOT / "cursor-bundle/kg/bin"))
        from kg_composite import composite_key  # noqa: E402

        kg_key = composite_key()
    except Exception:
        pass

    return {
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workspace": str(ROOT),
        "remotes": {"origin": "fork (push)", "upstream": UPSTREAM_ORG},
        "manifest": manifest,
        "kg_composite_key": kg_key,
        "summary": {
            "repos": len(repos),
            "dirty": dirty_n,
            "provisional_branches": prov_n,
            "upstream_behind": upstream_behind_n,
        },
        "repos": repos,
    }


def cmd_status(write: bool, as_json: bool) -> int:
    st = collect_status()
    if write:
        CURSOR.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(st, indent=2) + "\n", encoding="utf-8")
    if as_json:
        print(json.dumps(st, indent=2))
        return 0
    print(f"Git workspace ({st['summary']['repos']} repos) @ {st['updated_at']}")
    print(f"  remotes: origin=fork · upstream={UPSTREAM_ORG}")
    ov = st["manifest"].get("overrides") or {}
    if ov:
        print(f"  manifest overrides: {len(ov)} repo(s)")
    print(f"  dirty={st['summary']['dirty']} provisional={st['summary']['provisional_branches']} upstream_behind={st['summary']['upstream_behind']}")
    if st.get("kg_composite_key"):
        print(f"  kg key: {st['kg_composite_key'][:12]}…")
    for r, v in sorted(st["repos"].items()):
        tag = ""
        if v["dirty"]:
            tag += " dirty"
        if v["provisional"]:
            tag += " WIP"
        ub = v.get("upstream_behind")
        if ub is not None and ub > 0:
            tag += f" ↑{ub}vs-upstream"
        oa = v.get("origin_ahead")
        if oa is not None and oa > 0:
            tag += f" +{oa}vs-origin"
        short = r.replace("novopay-platform-", "np-").replace("novopay-", "n-")
        print(f"  {short:<28} {v['branch'][:36]:<36} @{v['sha']}{tag}")
    if write:
        print(f"\n→ {STATE_FILE.relative_to(ROOT)}")
    return 0


def cmd_manifest() -> int:
    print(json.dumps(load_manifest(), indent=2))
    return 0


def cmd_set_override(repo: str, branch: str) -> int:
    m = load_manifest()
    m.setdefault("overrides", {})[repo] = branch
    save_manifest(m)
    print(f"override: {repo} → {branch}")
    return 0


def cmd_clear_override(repo: str) -> int:
    m = load_manifest()
    m.get("overrides", {}).pop(repo, None)
    save_manifest(m)
    print(f"cleared override: {repo}")
    return 0


def main() -> int:
    args = sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd = args[0]
    if cmd == "status":
        write = "--write" in args
        as_json = "--json" in args
        return cmd_status(write, as_json)
    if cmd == "manifest":
        return cmd_manifest()
    if cmd == "set-override" and len(args) >= 3:
        return cmd_set_override(args[1], args[2])
    if cmd == "clear-override" and len(args) >= 2:
        return cmd_clear_override(args[1])
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
