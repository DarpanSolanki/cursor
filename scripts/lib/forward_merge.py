"""Declared forward-merge chain: where a fix travels without a hand-port.

`branch_train.py` proves ancestry from git. This module carries the *declared*
merge policy, which answers a different question: a branch that is MISSING a fix
today may still be downstream on the chain, so the fix arrives by forward merge
and must not be ported by hand.

    python3 scripts/lib/forward_merge.py order
    python3 scripts/lib/forward_merge.py downstream mfi_integration_v3.5.1.1
    python3 scripts/lib/forward_merge.py verify --repo trustt-platform-accounting --branch mfi_integration_v3.5.1.1
    python3 scripts/lib/forward_merge.py highest --repo trustt-platform-initial-setup
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHAINS = Path(__file__).with_name("forward_merge_chains.json")


def load() -> dict:
    return json.loads(CHAINS.read_text())


def canonical_order() -> list[str]:
    return load()["canonical_order"]


def position(branch: str) -> int | None:
    order = canonical_order()
    return order.index(branch) if branch in order else None


def downstream(branch: str) -> list[str]:
    index = position(branch)
    if index is None:
        return []
    return canonical_order()[index + 1 :]


def upstream_of(branch: str) -> list[str]:
    index = position(branch)
    if index is None:
        return []
    return canonical_order()[:index]


def lists_containing(branch: str) -> list[str]:
    return [entry["id"] for entry in load()["declared_lists"] if branch in entry["branches"]]


def coverage_note(branch: str) -> str:
    data = load()
    ids = lists_containing(branch)
    if not ids:
        return f"{branch} is not on any declared forward-merge list"
    missing = [entry["id"] for entry in data["declared_lists"] if branch not in entry["branches"]]
    if missing:
        return f"{branch} on {','.join(ids)}; absent from {','.join(missing)}"
    return f"{branch} on all declared lists"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL
    )
    return result.stdout.strip()


def _has_ref(repo: Path, ref: str) -> bool:
    return subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "-q", ref],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode == 0


def verify(repo: Path, branch: str, remote: str = "upstream") -> list[tuple[str, str]]:
    """Ancestry check of the declared chain: has each downstream branch absorbed `branch`?"""
    rows: list[tuple[str, str]] = []
    source = f"{remote}/{branch}"
    if not _has_ref(repo, source):
        return [(branch, "SOURCE-MISSING")]
    for target in downstream(branch):
        ref = f"{remote}/{target}"
        if not _has_ref(repo, ref):
            rows.append((target, "NO-BRANCH"))
            continue
        merged = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", source, ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        rows.append((target, "ABSORBED" if merged else "PENDING-FORWARD-MERGE"))
    return rows


def highest_present(repo: Path, remote: str = "upstream") -> str | None:
    for branch in reversed(canonical_order()):
        if _has_ref(repo, f"{remote}/{branch}"):
            return branch
    return None


def sha_travel(repo: Path, sha: str, branch: str, remote: str = "upstream") -> list[tuple[str, str]]:
    """For a fix sha landed on `branch`, classify every other chain branch."""
    rows: list[tuple[str, str]] = []
    for target in canonical_order():
        ref = f"{remote}/{target}"
        if not _has_ref(repo, ref):
            rows.append((target, "NO-BRANCH"))
            continue
        contains = subprocess.run(
            ["git", "-C", str(repo), "merge-base", "--is-ancestor", sha, ref],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
        if contains:
            rows.append((target, "HAS"))
        elif target in downstream(branch):
            rows.append((target, "ARRIVES-BY-FORWARD-MERGE"))
        else:
            rows.append((target, "NEEDS-EXPLICIT-PORT"))
    return rows


def resolve_repo(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("order")
    for name in ("downstream", "upstream", "coverage"):
        cmd = sub.add_parser(name)
        cmd.add_argument("branch")
    verify_cmd = sub.add_parser("verify")
    verify_cmd.add_argument("--repo", required=True)
    verify_cmd.add_argument("--branch", required=True)
    verify_cmd.add_argument("--remote", default="upstream")
    highest_cmd = sub.add_parser("highest")
    highest_cmd.add_argument("--repo", required=True)
    highest_cmd.add_argument("--remote", default="upstream")
    travel_cmd = sub.add_parser("travel")
    travel_cmd.add_argument("--repo", required=True)
    travel_cmd.add_argument("--sha", required=True)
    travel_cmd.add_argument("--branch", required=True)
    travel_cmd.add_argument("--remote", default="upstream")

    args = parser.parse_args(argv)

    if args.cmd == "order":
        for index, branch in enumerate(canonical_order()):
            print(f"{index:2d} {branch}")
        return 0
    if args.cmd == "downstream":
        for branch in downstream(args.branch):
            print(branch)
        print(f"# {coverage_note(args.branch)}", file=sys.stderr)
        return 0
    if args.cmd == "upstream":
        for branch in upstream_of(args.branch):
            print(branch)
        return 0
    if args.cmd == "coverage":
        print(coverage_note(args.branch))
        return 0
    if args.cmd == "verify":
        rows = verify(resolve_repo(args.repo), args.branch, args.remote)
        for target, state in rows:
            print(f"{state:24s} {args.remote}/{target}")
        return 0 if all(state in ("ABSORBED", "NO-BRANCH") for _, state in rows) else 2
    if args.cmd == "highest":
        branch = highest_present(resolve_repo(args.repo), args.remote)
        print(branch or "NONE")
        return 0 if branch else 1
    if args.cmd == "travel":
        rows = sha_travel(resolve_repo(args.repo), args.sha, args.branch, args.remote)
        for target, state in rows:
            print(f"{state:24s} {args.remote}/{target}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
