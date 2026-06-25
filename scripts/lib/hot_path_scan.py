#!/usr/bin/env python3
"""Heuristic hot-path perf scan — DAO-in-loop, stream-in-day-loop (workspace-wide)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

DAO_LINE = re.compile(
    r"\b(\w+DAOService|\w+Repository|\w+DaoService|jdbcTemplate|entityManager)\s*\.",
    re.IGNORECASE,
)
LOOP_LINE = re.compile(r"\b(while|for)\s*\(")
STREAM_IN_LOOP = re.compile(r"\.stream\s*\(")
METHOD_DEF = re.compile(
    r"^\s*(?:public|private|protected|static|\s)+[\w<>,\s\[\]]+\s+(\w+)\s*\([^;]*\)\s*\{?\s*$"
)


def _method_at_line(lines: list[str], line_idx: int) -> str | None:
    for j in range(line_idx, -1, -1):
        m = METHOD_DEF.match(lines[j])
        if m:
            return m.group(1)
    return None


def _methods_with_dao(lines: list[str]) -> dict[str, list[int]]:
    out: dict[str, list[int]] = {}
    for i, line in enumerate(lines):
        if line.strip().startswith("//"):
            continue
        if not DAO_LINE.search(line):
            continue
        name = _method_at_line(lines, i)
        if name:
            out.setdefault(name, []).append(i + 1)
    return out


def scan_java_file(path: Path, *, lookback: int = 30, loop_forward: int = 60) -> list[dict]:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
    except OSError:
        return []
    rel = str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)
    findings: list[dict] = []
    seen: set[tuple[str, int, str]] = set()

    def add(kind: str, line_no: int, snippet: str) -> None:
        key = (rel, line_no, kind)
        if key in seen:
            return
        seen.add(key)
        findings.append(
            {
                "file": rel,
                "line": line_no,
                "kind": kind,
                "snippet": snippet[:120],
            }
        )

    dao_methods = _methods_with_dao(lines)

    for i, line in enumerate(lines):
        if line.strip().startswith("//"):
            continue
        if not DAO_LINE.search(line):
            continue
        start = max(0, i - lookback)
        window = lines[start:i]
        if any(LOOP_LINE.search(w) for w in window):
            add("dao_in_loop", i + 1, line.strip())

    for i, line in enumerate(lines):
        if not LOOP_LINE.search(line):
            continue
        window = lines[i : min(len(lines), i + loop_forward)]
        blob = "\n".join(window)
        for mname, dao_lines in dao_methods.items():
            if mname == "if" or mname in ("for", "while", "switch"):
                continue
            if re.search(rf"\b{re.escape(mname)}\s*\(", blob):
                for dl in dao_lines:
                    add(
                        "dao_via_helper_from_loop",
                        dl,
                        f"{mname}() called near loop at line {i + 1}",
                    )

    for i, line in enumerate(lines):
        if not STREAM_IN_LOOP.search(line):
            continue
        start = max(0, i - lookback)
        window = lines[start:i]
        if not any(LOOP_LINE.search(w) for w in window):
            continue
        if "dueRows" in line or "dueDetails" in line or "installment" in line.lower():
            add("stream_scan_in_loop", i + 1, line.strip())

    return findings


def _is_java_ship(path: Path) -> bool:
    return path.suffix == ".java" and (
        "/src/main/java/" in str(path) or path.suffix == ".java"
    )


def paths_from_pending(root: Path) -> list[Path]:
    pending = root / ".cursor/.pending-ship-work.json"
    if not pending.is_file():
        return []
    try:
        data = json.loads(pending.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[Path] = []
    for rel in data.get("files") or []:
        p = root / rel if not str(rel).startswith("/") else Path(rel)
        if p.is_file() and _is_java_ship(p):
            out.append(p)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", default=[])
    ap.add_argument("--from-pending", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict", action="store_true", help="Exit 1 if any finding")
    args = ap.parse_args()

    paths: list[Path] = []
    for raw in args.path:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / raw
        if p.is_file():
            paths.append(p)
    if args.from_pending:
        paths.extend(paths_from_pending(ROOT))

    paths = list(dict.fromkeys(paths))
    all_findings: list[dict] = []
    for p in paths:
        all_findings.extend(scan_java_file(p))

    if args.json:
        print(json.dumps({"findings": all_findings, "files": len(paths)}, indent=2))
    elif all_findings:
        print("hot-path-scan WARN:")
        for f in all_findings:
            print(f"  [{f['kind']}] {f['file']}:{f['line']} — {f['snippet']}")
    else:
        print("hot-path-scan PASS")

    if args.strict and all_findings:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
