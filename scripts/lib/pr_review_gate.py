#!/usr/bin/env python3
"""PR-review machine gate — fail-closed on the pr-review proof contract.

The `pr-review` skill states a strict evidence contract (provenance complete, one
SHA set, CONFIRMED-only findings, questions never directives, verdict consistent
with findings and train status). Until now that contract was prose: nothing failed
when a review skipped the final freshness re-check or promoted a SUSPECTED item to
a directive. Every other contract in this workspace is machine-enforced; this makes
the review contract match.

Usage:
    python3 scripts/lib/pr_review_gate.py --report REPORT.md --artifacts DIR

Exit 0 = contract satisfied. Exit 1 = contract violated (review must not be sent).
Exit 2 = gate could not run (missing artifacts) — also not a pass.

Pure functions take plain text/dicts so they are unit-testable without gh or git.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

VERDICTS = ("REQUEST CHANGES", "NOT VERIFIED", "APPROVE", "COMMENT")
BLOCKER_SEVERITIES = ("BLOCKING", "MAJOR")
SECTION_NAMES = (
    "Provenance",
    "Scope and requirements",
    "Claim status",
    "Findings",
    "Questions",
    "Verification",
    "Residual risks",
)
REQUIRED_PROVENANCE = (
    "PR:",
    "Repository:",
    "Base:",
    "Head:",
    "Environment:",
    "Jira:",
    "Train status:",
    "Collected:",
    "Freshness:",
)
SELF_REVIEW_RE = re.compile(
    r"Self-review:\s*attempted to falsify each finding", re.IGNORECASE
)
TAG_RE = re.compile(r"\[(?P<severity>[A-Z-]+)\]\[(?P<confidence>[A-Z-]+)\]")
SHA_RE = re.compile(r"\b([0-9a-f]{7,40})\b")
FILE_LINE_RE = re.compile(r"[\w./-]+\.\w+:\d+")
CHECK_ID_RE = re.compile(r"\b(check|ci|job|run|log|test|workflow)[:=]\S+", re.IGNORECASE)


def split_sections(text: str) -> dict[str, list[str]]:
    """Group report lines under their section heading; unheaded lines land in ''."""
    sections: dict[str, list[str]] = {"": []}
    current = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if stripped in SECTION_NAMES:
            current = stripped
            sections.setdefault(current, [])
            continue
        sections.setdefault(current, []).append(raw)
    return sections


def entry_lines(section: list[str]) -> list[str]:
    """Numbered or bulleted entries only — prose and blank lines are not findings."""
    out = []
    for raw in section:
        stripped = raw.strip()
        if not stripped:
            continue
        if re.match(r"^(\d+\.|[-*])\s+", stripped):
            out.append(stripped)
    return out


def parse_verdict(text: str) -> str | None:
    match = re.search(r"^Verdict:\s*(.+?)\s*$", text, re.MULTILINE)
    if not match:
        return None
    value = match.group(1).strip()
    for verdict in VERDICTS:
        if value.upper().startswith(verdict):
            return verdict
    return None


def parse_train_status(text: str) -> str | None:
    match = re.search(r"^-?\s*Train status:\s*([A-Z]+)", text, re.MULTILINE)
    return match.group(1).strip() if match else None


def freshness_errors(artifacts: dict) -> list[str]:
    """One SHA set only: initial and final collection must agree on base and head."""
    errors: list[str] = []
    freshness = artifacts.get("freshness")
    if not isinstance(freshness, dict):
        return ["freshness.json missing or unreadable — provenance cannot be proven"]
    if str(freshness.get("status", "")).upper() != "VERIFIED":
        errors.append(f"freshness status is {freshness.get('status')!r}, not VERIFIED")
    for side in ("base", "head"):
        block = freshness.get(side)
        if not isinstance(block, dict):
            errors.append(f"freshness.{side} missing")
            continue
        shas = {
            key: value
            for key, value in block.items()
            if key.endswith("_sha") and value
        }
        if len(shas) < 2:
            errors.append(f"freshness.{side} has no initial/final SHA pair to compare")
            continue
        if len(set(shas.values())) != 1:
            errors.append(
                f"freshness.{side} SHAs disagree across collection: {sorted(set(shas.values()))}"
            )
    return errors


def artifact_shas(artifacts: dict) -> dict[str, str]:
    provenance = artifacts.get("provenance") or {}
    target = provenance.get("target") or {}
    out = {}
    for side in ("base", "head"):
        sha = (target.get(side) or {}).get("sha")
        if sha:
            out[side] = str(sha)
    return out


def provenance_errors(text: str, artifacts: dict) -> list[str]:
    """Report must carry every provenance label and cite the collected SHAs."""
    errors: list[str] = []
    sections = split_sections(text)
    block = "\n".join(sections.get("Provenance", []))
    if not block.strip():
        return ["Provenance section is missing"]
    for label in REQUIRED_PROVENANCE:
        if label not in block:
            errors.append(f"Provenance is missing {label.rstrip(':')!r}")

    cited = {sha.lower() for sha in SHA_RE.findall(block)}
    for side, sha in artifact_shas(artifacts).items():
        if not any(sha.lower().startswith(seen) for seen in cited):
            errors.append(
                f"Provenance does not cite the collected {side} SHA {sha[:12]} — "
                "evidence may come from a different SHA set"
            )
    return errors


def finding_errors(sections: dict[str, list[str]]) -> list[str]:
    """Findings are CONFIRMED-only and must carry file:line or a tied check id."""
    errors: list[str] = []
    for line in entry_lines(sections.get("Findings", [])):
        tag = TAG_RE.search(line)
        if not tag:
            errors.append(f"Finding has no [SEVERITY][CONFIDENCE] tag: {line[:90]}")
            continue
        severity = tag.group("severity")
        confidence = tag.group("confidence")
        if confidence != "CONFIRMED":
            errors.append(
                f"Finding is {confidence}, not CONFIRMED — belongs under Questions "
                f"or missing evidence: {line[:90]}"
            )
        if severity == "QUESTION":
            errors.append(f"QUESTION severity cannot sit under Findings: {line[:90]}")
        if not (FILE_LINE_RE.search(line) or CHECK_ID_RE.search(line)):
            errors.append(
                f"Finding cites no file:line or check id: {line[:90]}"
            )
    return errors


def question_errors(sections: dict[str, list[str]]) -> list[str]:
    """Questions stay neutral: SUSPECTED tag, interrogative, never an instruction."""
    errors: list[str] = []
    for line in entry_lines(sections.get("Questions", [])):
        tag = TAG_RE.search(line)
        if not tag:
            errors.append(f"Question has no [QUESTION][SUSPECTED] tag: {line[:90]}")
            continue
        if tag.group("severity") != "QUESTION":
            errors.append(f"Question severity must be QUESTION: {line[:90]}")
        if tag.group("confidence") != "SUSPECTED":
            errors.append(
                f"Question confidence must be SUSPECTED, got {tag.group('confidence')}: {line[:90]}"
            )
        if not line.rstrip().endswith("?"):
            errors.append(
                f"Question is phrased as a directive, not a question: {line[:90]}"
            )
    return errors


def confirmed_blockers(sections: dict[str, list[str]]) -> list[str]:
    out = []
    for line in entry_lines(sections.get("Findings", [])):
        tag = TAG_RE.search(line)
        if tag and tag.group("confidence") == "CONFIRMED" and tag.group("severity") in BLOCKER_SEVERITIES:
            out.append(line)
    return out


def verdict_errors(text: str) -> list[str]:
    errors: list[str] = []
    verdict = parse_verdict(text)
    if verdict is None:
        return ["Verdict line missing or not one of the four taxonomy values"]
    sections = split_sections(text)
    blockers = confirmed_blockers(sections)
    if blockers and verdict in ("APPROVE", "COMMENT"):
        errors.append(
            f"Verdict {verdict} contradicts {len(blockers)} CONFIRMED blocking/major "
            "finding(s) — use REQUEST CHANGES"
        )
    if blockers and verdict == "NOT VERIFIED":
        errors.append(
            "An evidenced blocker cannot be downgraded to NOT VERIFIED — use REQUEST CHANGES"
        )
    train = parse_train_status(text)
    if verdict == "APPROVE" and train in ("STALE", "MIXED"):
        errors.append(f"APPROVE forbidden while train status is {train}")
    return errors


def self_review_errors(text: str) -> list[str]:
    if SELF_REVIEW_RE.search(text):
        return []
    return ["Self-review falsification line is missing"]


def gate_errors(text: str, artifacts: dict) -> list[str]:
    sections = split_sections(text)
    return [
        *freshness_errors(artifacts),
        *provenance_errors(text, artifacts),
        *finding_errors(sections),
        *question_errors(sections),
        *verdict_errors(text),
        *self_review_errors(text),
    ]


def load_artifacts(directory: Path) -> dict:
    out: dict = {}
    for name in ("freshness", "provenance", "metadata"):
        path = directory / f"{name}.json"
        if path.is_file():
            try:
                out[name] = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                out[name] = None
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="Drafted review report file")
    parser.add_argument(
        "--artifacts", required=True, help="Collector output directory from pr-review.sh"
    )
    args = parser.parse_args(argv)

    report_path = Path(args.report)
    artifacts_dir = Path(args.artifacts)
    if not report_path.is_file():
        print(f"pr-review-gate: report not found: {report_path}", file=sys.stderr)
        return 2
    if not artifacts_dir.is_dir():
        print(f"pr-review-gate: artifacts not found: {artifacts_dir}", file=sys.stderr)
        return 2

    artifacts = load_artifacts(artifacts_dir)
    if "freshness" not in artifacts or "provenance" not in artifacts:
        print(
            "pr-review-gate: collector artifacts incomplete (freshness/provenance) — "
            "re-run scripts/bin/pr-review.sh",
            file=sys.stderr,
        )
        return 2

    errors = gate_errors(report_path.read_text(encoding="utf-8"), artifacts)
    if errors:
        print("PR-REVIEW GATE: FAIL")
        for error in errors:
            print(f"  - {error}")
        return 1
    print("PR-REVIEW GATE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
