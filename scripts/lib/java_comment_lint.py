#!/usr/bin/env python3
"""Fail-closed Java comment verbosity lint (DPI / money hot paths).

Prose-only guidance in feedback_keep_code_simple was ignored; this gate blocks
narrative comment blocks on ship when pending files match DPI/money Java paths.

Rules (any match → FAIL):
  consecutive_slashes — 3+ consecutive // lines (agent narrative blocks)
  ticket_or_essay — TDPQA/SDCP ticket ids, Sheet rule, mirrors/parity essays, date-arrow examples
  long_essay_javadoc — javadoc with >2 body lines AND essay markers (bare long class docs allowed)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"

DPI_PATH = re.compile(r"(?i)(/dpi/|/Dpi|/DPI|Dpi[A-Z]|DPI[A-Z])")
TICKET_OR_ESSAY = re.compile(
    r"(?i)\bTDPQA-\d+\b|\bSDCP-\d+\b|Sheet rule|\bmirrors\b|\bparity\b|"
    r"e\.g\.|May\d+\s*→|permanent fix|agent added"
)
SLASH_COMMENT = re.compile(r"^\s*//(.*)$")
JAVADOC_START = re.compile(r"^\s*/\*\*")
BLOCK_END = re.compile(r"\*/")


def is_dpi_java(path: Path | str) -> bool:
    s = str(path).replace("\\", "/")
    return s.endswith(".java") and bool(DPI_PATH.search(s))


def _scan_text(rel: str, text: str) -> list[dict]:
    lines = text.splitlines()
    findings: list[dict] = []
    i = 0
    n = len(lines)

    def add(kind: str, line_no: int, snippet: str) -> None:
        findings.append(
            {
                "file": rel,
                "line": line_no,
                "kind": kind,
                "snippet": snippet.strip()[:160],
            }
        )

    while i < n:
        line = lines[i]
        m = SLASH_COMMENT.match(line)
        if m:
            block = [m.group(1)]
            start = i + 1
            j = i + 1
            while j < n:
                m2 = SLASH_COMMENT.match(lines[j])
                if not m2:
                    break
                block.append(m2.group(1))
                j += 1
            joined = " ".join(block)
            if len(block) >= 3:
                add("consecutive_slashes", start, joined)
            elif TICKET_OR_ESSAY.search(joined):
                add("ticket_or_essay", start, joined)
            i = j
            continue

        if JAVADOC_START.match(line):
            start = i + 1
            body: list[str] = []
            j = i
            while j < n:
                cur = lines[j]
                body_line = re.sub(r"^\s*\* ?", "", cur)
                if j > i and not BLOCK_END.search(cur):
                    stripped = body_line.strip()
                    if stripped and stripped not in ("/**", "*/") and not stripped.startswith("@"):
                        if not stripped.startswith("/*"):
                            body.append(stripped)
                if BLOCK_END.search(cur):
                    j += 1
                    break
                j += 1
            joined = " ".join(body)
            if TICKET_OR_ESSAY.search(joined):
                kind = "long_essay_javadoc" if len(body) > 2 else "ticket_or_essay"
                add(kind, start, joined)
            i = j
            continue

        if "/*" in line and "*/" in line and not line.strip().startswith("*"):
            inner = line[line.find("/*") + 2 : line.rfind("*/")]
            if TICKET_OR_ESSAY.search(inner):
                add("ticket_or_essay", i + 1, inner)
        i += 1

    return findings


def scan_file(path: Path, *, root: Path = ROOT) -> list[dict]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []
    try:
        rel = str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(path)
    return _scan_text(rel, text)


def pending_java_paths(pending_path: Path = PENDING, *, root: Path = ROOT) -> list[Path]:
    if not pending_path.is_file():
        return []
    try:
        data = json.loads(pending_path.read_text())
    except (OSError, json.JSONDecodeError):
        return []
    out: list[Path] = []
    for f in data.get("files") or []:
        p = root / f if not Path(f).is_absolute() else Path(f)
        if is_dpi_java(p):
            out.append(p)
    return out


def scan_paths(paths: list[Path], *, root: Path = ROOT) -> list[dict]:
    findings: list[dict] = []
    for p in paths:
        if p.is_file():
            findings.extend(scan_file(p, root=root))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("paths", nargs="*", help="Java files or directories to scan")
    ap.add_argument("--from-pending", action="store_true", help="Scan DPI Java from pending ship work")
    ap.add_argument("--dpi-tree", action="store_true", help="Scan accounting **/dpi/**/*.java and Dpi*.java")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    paths: list[Path] = []
    if args.from_pending:
        paths.extend(pending_java_paths())
    if args.dpi_tree:
        acct = ROOT / "trustt-platform-accounting"
        if acct.is_dir():
            paths.extend(acct.glob("**/dpi/**/*.java"))
            paths.extend(acct.glob("**/Dpi*.java"))
            paths.extend(acct.glob("**/DPI*.java"))
    for raw in args.paths:
        p = Path(raw)
        if not p.is_absolute():
            p = ROOT / p
        if p.is_dir():
            paths.extend(p.rglob("*.java"))
        else:
            paths.append(p)

    # de-dupe
    uniq: list[Path] = []
    seen: set[str] = set()
    for p in paths:
        key = str(p.resolve()) if p.exists() else str(p)
        if key in seen:
            continue
        seen.add(key)
        if is_dpi_java(p) or args.paths:
            uniq.append(p)

    findings = scan_paths(uniq)
    if args.json:
        print(json.dumps({"findings": findings, "files": len(uniq)}, indent=2))
    elif findings:
        print(f"java-comment-lint FAIL: {len(findings)} finding(s) in {len(uniq)} file(s)", file=sys.stderr)
        for f in findings:
            print(f"  {f['file']}:{f['line']} [{f['kind']}] {f['snippet']}", file=sys.stderr)
        print(
            "Keep only concise non-obvious business invariants; strip narrative/parity essays.",
            file=sys.stderr,
        )
        return 1
    else:
        print(f"java-comment-lint PASS ({len(uniq)} file(s))")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
