#!/usr/bin/env python3
"""Reuse-query machine gate — fail-closed for any *Repository.java / *DAOService.java query change.

Standing workspace gap (2026-07-17): a repository SQL/method change shipped before the
reuse-queries ladder (reuse existing + Java filter → extend existing → new @Query last)
was proven. Soft rules were skipped. This gate makes it machine-enforced.

Trigger: a pending ship file whose basename ends `Repository.java` / `DAOService.java`
(any case) AND whose diff adds/changes query semantics — `@Query`, native SQL text,
`ORDER BY`, `LIMIT`, `WHERE`, `SELECT`/`JOIN`/`GROUP BY`, or a finder-method signature.

When triggered, `.cursor/.ship-discipline.json` MUST carry a `reuse_query` block:
  {
    "reuse_queries_step": 1|2|3,          # ladder step actually used
    "existing_methods_checked": [ ... ],  # grep of repo/DAO methods considered (non-empty)
    "callers_checked": [ ... ],           # call sites verified for the changed method (non-empty)
    "new_query_justification": "...",     # REQUIRED when step==3 (why 1 & 2 cannot work)
    "performance_impact": "..."           # index/scan/limit note for the change
  }

Pure functions (`diff_query_signals`, `reuse_query_block_errors`) are unit-testable
without git; git access is isolated behind an injectable `diff_getter`.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Callable, Iterable

ROOT = Path(__file__).resolve().parents[2]

# Query-semantic markers scanned on changed (+/-) diff lines.
_MARKERS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("@Query", re.compile(r"@Query\b")),
    ("nativeQuery", re.compile(r"\bnativeQuery\b", re.I)),
    ("ORDER BY", re.compile(r"\border\s+by\b", re.I)),
    ("LIMIT", re.compile(r"\blimit\b", re.I)),
    ("OFFSET", re.compile(r"\boffset\b", re.I)),
    ("WHERE", re.compile(r"\bwhere\b", re.I)),
    ("SELECT", re.compile(r"\bselect\b", re.I)),
    ("JOIN", re.compile(r"\bjoin\b", re.I)),
    ("GROUP BY", re.compile(r"\bgroup\s+by\b", re.I)),
    ("HAVING", re.compile(r"\bhaving\b", re.I)),
    ("UNION", re.compile(r"\bunion\b", re.I)),
)

# Finder-method declaration in a repository interface (return type + finder name + args).
_FINDER_SIG = re.compile(
    r"^\s*(?:public\s+|default\s+|abstract\s+)*"
    r"[\w<>,.\[\]?\s]+?\s+"  # return type
    r"(find|get|count|exists|search|read|load|fetch)\w*\s*\(",
    re.I,
)


def is_repo_or_dao_file(path: str) -> bool:
    base = Path(path).name.lower()
    return base.endswith("repository.java") or base.endswith("daoservice.java")


def _changed_lines(diff_text: str) -> Iterable[str]:
    for line in diff_text.splitlines():
        if not line:
            continue
        if line.startswith(("+++", "---", "diff ", "index ", "@@")):
            continue
        if line[0] in "+-":
            yield line[1:]


def diff_query_signals(diff_text: str) -> list[str]:
    """Return sorted, de-duplicated query-semantic signals present on changed lines.

    Empty list => no query semantics changed (gate does not trigger for this file).
    """
    if not diff_text:
        return []
    found: set[str] = set()
    for body in _changed_lines(diff_text):
        for name, pat in _MARKERS:
            if pat.search(body):
                found.add(name)
        if _FINDER_SIG.search(body) and body.rstrip().endswith((";", "{")):
            # New/removed finder declaration changes query surface even without inline SQL.
            found.add("finder-signature")
    return sorted(found)


def _repo_and_rel(path: str) -> tuple[str, str]:
    norm = path.replace("\\", "/").lstrip("./")
    parts = norm.split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "", norm


def default_diff_getter(root: Path = ROOT) -> Callable[[str, str], str]:
    """Diff getter combining committed-vs-upstream and working-tree diffs for a repo file."""

    def _get(repo: str, relpath: str) -> str:
        repo_dir = root / repo if repo else root
        if not (repo_dir / ".git").is_dir():
            return ""
        chunks: list[str] = []
        for args in (
            ["diff", "@{upstream}...HEAD", "--", relpath],
            ["diff", "HEAD", "--", relpath],
            ["diff", "--", relpath],
        ):
            try:
                r = subprocess.run(
                    ["git", "-C", str(repo_dir), *args],
                    capture_output=True,
                    text=True,
                    check=False,
                )
            except OSError:
                continue
            if r.returncode == 0 and r.stdout:
                chunks.append(r.stdout)
        return "\n".join(chunks)

    return _get


def scan_files(
    files: list[str],
    *,
    root: Path = ROOT,
    diff_getter: Callable[[str, str], str] | None = None,
) -> list[dict]:
    """Return [{file, signals}] for pending repo/DAO files with query-semantic diffs."""
    getter = diff_getter or default_diff_getter(root)
    triggered: list[dict] = []
    for f in files or []:
        if not is_repo_or_dao_file(f):
            continue
        repo, rel = _repo_and_rel(f)
        signals = diff_query_signals(getter(repo, rel))
        if signals:
            triggered.append({"file": f, "signals": signals})
    return triggered


_VALID_STEPS = frozenset({1, 2, 3, "1", "2", "3"})


def reuse_query_block_errors(block: object) -> list[str]:
    """Validate a `reuse_query` discipline block. Empty list => valid."""
    errors: list[str] = []
    if not isinstance(block, dict):
        return ["reuse_query block missing — add it to .cursor/.ship-discipline.json"]

    step = block.get("reuse_queries_step")
    if step not in _VALID_STEPS:
        errors.append("reuse_queries_step must be 1, 2, or 3")
    existing = block.get("existing_methods_checked")
    if not isinstance(existing, list) or not existing:
        errors.append("existing_methods_checked must be a non-empty list (methods grepped)")
    callers = block.get("callers_checked")
    if not isinstance(callers, list) or not callers:
        errors.append("callers_checked must be a non-empty list (call sites verified)")
    perf = block.get("performance_impact")
    if not isinstance(perf, str) or len(perf.strip()) < 6:
        errors.append("performance_impact required (index/scan/limit note)")
    if str(step) == "3":
        just = block.get("new_query_justification")
        if not isinstance(just, str) or len(just.strip()) < 12:
            errors.append(
                "new_query_justification required for step 3 (why reuse + extend cannot work)"
            )
    return errors


def check(
    pending: dict,
    disc: dict,
    *,
    root: Path = ROOT,
    diff_getter: Callable[[str, str], str] | None = None,
) -> list[str]:
    """Return list of gate errors (empty => pass). Fail-closed only when triggered."""
    files = (pending or {}).get("files") or []
    triggered = scan_files(files, root=root, diff_getter=diff_getter)
    if not triggered:
        return []
    names = ", ".join(f"{t['file']} [{'/'.join(t['signals'])}]" for t in triggered)
    block_errors = reuse_query_block_errors((disc or {}).get("reuse_query"))
    if block_errors:
        return [f"repository/DAO query change needs reuse_query proof — {names}"] + [
            f"  reuse_query.{e}" for e in block_errors
        ]
    return []
