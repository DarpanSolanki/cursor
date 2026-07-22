"""Fast branch-mix warning used by ship-loop tooling."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TRAIN = re.compile(r"^mfi_(?:integration|release)_v(?P<version>\d+(?:\.\d+)*)$")


def active_branch_mix_note() -> str:
    """Return a concise advisory; never mutate branches or block the ship loop."""
    by_version: dict[str, list[str]] = {}
    wip: list[str] = []
    for repo in sorted(ROOT.iterdir()):
        if not (repo / ".git").exists():
            continue
        result = subprocess.run(
            ["git", "-C", str(repo), "branch", "--show-current"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        branch = result.stdout.strip()
        match = TRAIN.match(branch)
        if match:
            by_version.setdefault(match.group("version"), []).append(repo.name)
        elif branch:
            wip.append(f"{repo.name}:{branch}")
    if len(by_version) <= 1 and not wip:
        return ""
    trains = ", ".join(
        f"{version}({len(repos)})"
        for version, repos in sorted(by_version.items())
    )
    suffix = f"; WIP={len(wip)}" if wip else ""
    return (
        "⚠ mixed branch topology: "
        f"trains={trains or 'none'}{suffix}. "
        "Cross-service conclusions require aligned trains; "
        "use `kg fixed-elsewhere` for read-only cross-branch discovery."
    )

