"""Machine check for the three loops in `.cursor/rules/40-knowledge-upkeep.mdc`.

The rule says every change closes KG, testing suite and reference docs. Until now that was
prose: nothing failed when a loop was skipped, so knowledge only got written when someone
asked for it. This classifies what the working tree actually changed and names the loops
left open.

    python3 scripts/lib/knowledge_loop_gate.py            # report
    python3 scripts/lib/knowledge_loop_gate.py --strict   # exit 2 when a required loop is open
    python3 scripts/lib/knowledge_loop_gate.py --json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CODE_MARKERS = ("/src/main/", "/src/test/", "/deploy/application/", "/flyway/")
SUITE_MARKERS = (
    "scripts/testing/registry.json",
    "scripts/testing/flowtest/",
    "scripts/dpic/",
    "scripts/dcf_sanity/",
)
KG_MARKERS = (
    "cursor-bundle/brain/changelog/CHANGELOG.md",
    ".cursor/changelog.md",
)
DOCS_MARKERS = (
    "cursor-bundle/memory/",
    ".cursor/rules/",
    ".cursor/skills/",
    ".cursor/gaps-and-risks.md",
)
HARNESS_MARKERS = ("scripts/bin/", "scripts/lib/", ".cursor/hooks/")


def _changed_in(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    rows = []
    for line in result.stdout.splitlines():
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if path:
            prefix = "" if repo == ROOT else f"{repo.name}/"
            rows.append(prefix + path)
    return rows


PENDING = ROOT / ".cursor/.pending-ship-work.json"


def session_files() -> list[str]:
    """Files this session touched.

    Two sources, because neither is complete on its own: the session record only sees edits
    made through the tool hooks (a scripted write is invisible to it), and a whole-tree scan
    across every repo blames this session for other repos' pre-existing dirt. So: tracked
    session files, plus the workspace repo's own dirty tree, and service repos only when the
    session record already names them.
    """
    tracked: list[str] = []
    if PENDING.is_file():
        try:
            tracked = json.loads(PENDING.read_text()).get("files") or []
        except (json.JSONDecodeError, OSError):
            tracked = []

    files = list(dict.fromkeys(tracked + _changed_in(ROOT)))
    named_repos = {path.split("/", 1)[0] for path in tracked if "/" in path}
    for repo in sorted(ROOT.iterdir()):
        if repo.name in named_repos and repo.is_dir() and (repo / ".git").exists():
            files.extend(_changed_in(repo))
    return list(dict.fromkeys(files))


def classify(files: list[str]) -> dict[str, list[str]]:
    buckets: dict[str, list[str]] = {"code": [], "kg": [], "suite": [], "docs": [], "harness": []}
    for path in files:
        if any(marker in path for marker in CODE_MARKERS):
            buckets["code"].append(path)
        if any(path.startswith(marker) or marker in path for marker in SUITE_MARKERS):
            buckets["suite"].append(path)
        if any(path.endswith(marker) or marker in path for marker in KG_MARKERS):
            buckets["kg"].append(path)
        if any(marker in path for marker in DOCS_MARKERS):
            buckets["docs"].append(path)
        if any(path.startswith(marker) for marker in HARNESS_MARKERS):
            buckets["harness"].append(path)
    return buckets


def evaluate(buckets: dict[str, list[str]]) -> tuple[list[str], list[str]]:
    """Return (required-and-open, advisory-and-open)."""
    open_required: list[str] = []
    open_advisory: list[str] = []
    touched_behaviour = bool(buckets["code"]) or bool(buckets["harness"])
    if not touched_behaviour:
        return [], []
    if not buckets["kg"]:
        open_required.append("KG — no changelog entry (brain CHANGELOG / .cursor/changelog.md)")
    if buckets["code"] and not buckets["suite"]:
        open_required.append("suite — code changed with no registry/flowtest change")
    if not buckets["docs"]:
        open_advisory.append("docs — no memory/rule/skill/gaps update")
    return open_required, open_advisory


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    buckets = classify(session_files())
    open_required, open_advisory = evaluate(buckets)

    if args.json:
        print(json.dumps({
            "buckets": {k: v[:10] for k, v in buckets.items()},
            "open_required": open_required,
            "open_advisory": open_advisory,
        }, indent=1))
    else:
        for name in ("code", "harness", "kg", "suite", "docs"):
            count = len(buckets[name])
            mark = "✓" if count else "·"
            print(f"  {mark} {name:8s} {count} file(s)")
        for item in open_required:
            print(f"OPEN (required)  {item}")
        for item in open_advisory:
            print(f"OPEN (advisory)  {item}")
        if not open_required and not open_advisory:
            print("Knowledge updated: all three loops closed for this change set.")

    if args.strict and open_required:
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
