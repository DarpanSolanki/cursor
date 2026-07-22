#!/usr/bin/env python3
"""Canonical local-folder → GitHub repo name map (org rename 2026-07).

As of 2026-07-15, local clone folders match GitHub repo names (`trustt-*`).
Legacy local names (`novopay-*`, old codegen folder) still map for URL helpers.
Do NOT use for Java package renaming (`in.novopay.*` stays).

CLI:
  python3 scripts/lib/github_repo_map.py map <local_dir>
  python3 scripts/lib/github_repo_map.py urls <local_dir> [fork_user]
  python3 scripts/lib/github_repo_map.py verify [--root PATH]
  python3 scripts/lib/github_repo_map.py table
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

UPSTREAM_ORG = "trusttai"
DEFAULT_FORK_USER = "DarpanSolanki"

# Legacy local folder names → GitHub repo (= current local folder).
# Current folders are identity (folder name == GitHub name).
_LEGACY_LOCAL: dict[str, str] = {
    "novopay-platform-accounting-v2": "trustt-platform-accounting",
    "novopay-mfi-los": "trustt-platform-los",
    "novopay-platform-actor": "trustt-platform-actor",
    "novopay-platform-api-gateway": "trustt-platform-api-gateway",
    "novopay-platform-approval": "trustt-platform-approval",
    "novopay-platform-audit": "trustt-platform-audit",
    "novopay-platform-authorization": "trustt-platform-authorization",
    "novopay-platform-batch": "trustt-platform-batch",
    "novopay-platform-dependency-mgmt": "trustt-platform-dependency-mgmt",
    "novopay-platform-dms": "trustt-platform-dms",
    "novopay-platform-initial-setup": "trustt-platform-initial-setup",
    "novopay-platform-lib": "trustt-platform-lib",
    "novopay-platform-masterdata-management": "trustt-platform-masterdata-management",
    "novopay-platform-notifications": "trustt-platform-notifications",
    "novopay-platform-payments": "trustt-platform-payments",
    "novopay-platform-simulators": "trustt-platform-simulators",
    "novopay-platform-task": "trustt-platform-task",
    "novopay-platform-webapp": "trustt-platform-webapp",
    "trustt-platform-ai-codegen-artifacts": "trustt-platform-ai-codegen-artifacts-java",
}


def github_upstream_repo(local_dir: str) -> str:
    """Local clone directory basename → GitHub repo name (origin + upstream)."""
    if local_dir in _LEGACY_LOCAL:
        return _LEGACY_LOCAL[local_dir]
    if local_dir.startswith("novopay-"):
        return "trustt-" + local_dir[len("novopay-") :]
    return local_dir


def github_fork_repo(local_dir: str) -> str:
    """Forks under DarpanSolanki match upstream names (verified 2026-07-15)."""
    return github_upstream_repo(local_dir)


def github_upstream_url(local_dir: str, org: str = UPSTREAM_ORG) -> str:
    return f"https://github.com/{org}/{github_upstream_repo(local_dir)}.git"


def github_fork_url(local_dir: str, user: str = DEFAULT_FORK_USER) -> str:
    return f"https://github.com/{user}/{github_fork_repo(local_dir)}.git"


def list_workspace_repos(root: Path) -> list[str]:
    names: list[str] = []
    for pat in ("novopay-*", "trustt-*"):
        for d in sorted(root.glob(pat)):
            if (d / ".git").is_dir():
                names.append(d.name)
    return names


def _remote_url(repo_dir: Path, remote: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(repo_dir), "remote", "get-url", remote],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def verify(root: Path) -> int:
    """Compare live remotes to expected URLs. Exit 0 if all match."""
    fail = 0
    rows = list_workspace_repos(root)
    if not rows:
        print(f"No novopay-*/trustt-* git repos under {root}", file=sys.stderr)
        return 1
    print(f"{'LOCAL':<42} {'MAP':<42} MATCH")
    for name in rows:
        mapped = github_upstream_repo(name)
        expect_u = github_upstream_url(name)
        expect_o = github_fork_url(name)
        d = root / name
        got_u = _remote_url(d, "upstream")
        got_o = _remote_url(d, "origin")

        def _same(got: str, expect: str, owner: str) -> bool:
            if not got:
                return False
            g, e = got.rstrip("/"), expect.rstrip("/")
            if g == e:
                return True
            # Accept SSH: git@host:owner/repo.git
            return mapped in g and owner in g and g.endswith(f"{mapped}.git")

        ok_u = _same(got_u, expect_u, "trusttai")
        ok_o = _same(got_o, expect_o, "DarpanSolanki")
        status = "OK" if ok_u and ok_o else "MISMATCH"
        if status != "OK":
            fail += 1
        print(f"{name:<42} {mapped:<42} {status}")
        if status != "OK":
            print(f"  expect origin:   {expect_o}")
            print(f"  got    origin:   {got_o or 'MISSING'}")
            print(f"  expect upstream: {expect_u}")
            print(f"  got    upstream: {got_u or 'MISSING'}")
    print(f"\n{len(rows) - fail}/{len(rows)} remotes match map")
    return 1 if fail else 0


def table() -> None:
    print("| Local folder | GitHub repo (origin + upstream) |")
    print("|---|---|")
    samples = [
        "trustt-platform-actor",
        "trustt-platform-accounting",
        "trustt-platform-los",
        "trustt-platform-reporting",
        "trustt-platform-ai-codegen-artifacts-java",
        "novopay-platform-accounting-v2",  # legacy alias
    ]
    for s in samples:
        print(f"| `{s}` | `{github_upstream_repo(s)}` |")
    print()
    print(f"Org upstream: `{UPSTREAM_ORG}` · Fork user: `{DEFAULT_FORK_USER}`")
    print("Rule: local folder == GitHub name; legacy novopay-* aliases retained.")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("map", help="Print GitHub repo name for local dir")
    m.add_argument("local_dir")

    u = sub.add_parser("urls", help="Print origin + upstream HTTPS URLs")
    u.add_argument("local_dir")
    u.add_argument("fork_user", nargs="?", default=DEFAULT_FORK_USER)

    v = sub.add_parser("verify", help="Compare live remotes to map")
    v.add_argument("--root", type=Path, default=None)

    sub.add_parser("table", help="Print mapping summary")

    args = p.parse_args(argv)
    if args.cmd == "map":
        print(github_upstream_repo(args.local_dir))
        return 0
    if args.cmd == "urls":
        print(f"origin={github_fork_url(args.local_dir, args.fork_user)}")
        print(f"upstream={github_upstream_url(args.local_dir)}")
        return 0
    if args.cmd == "verify":
        root = args.root or Path(__file__).resolve().parents[2]
        return verify(root)
    if args.cmd == "table":
        table()
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
