#!/usr/bin/env python3
"""Fail-closed Java comment verbosity lint (DPI / money hot paths).

Prose-only guidance in feedback_keep_code_simple was ignored; this gate blocks
narrative comment blocks on ship when pending files match DPI/money Java paths.

Rules (any match → FAIL):
  consecutive_slashes — 3+ consecutive // lines (agent narrative blocks)
  ticket_or_essay — TDPQA/SDCP ticket ids, Sheet rule, mirrors/parity essays, date-arrow examples
  long_essay_javadoc — javadoc with >2 body lines AND essay markers (bare long class docs allowed)
  added_comment_volume (--diff) — >2 comment lines ADDED to one file in a diff

The shape rules above all key on a single block being long or essay-like. They pass
a change that sprinkles many short 1-2 line javadocs, which is the shape agents
actually produce (TDPQA-234: 16 comment lines over 90 code lines, all rules PASS).
--diff closes that by counting added comment lines per file instead of per block.
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


MAX_ADDED_COMMENT_LINES = 2
_ADDED_COMMENT = re.compile(r"^\+\s*(//|/\*|\*[^/])")
_ADDED_CODE = re.compile(r"^\+(?!\+\+)")


def diff_findings(repo: Path, base: str) -> list[dict]:
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(repo), "diff", "--unified=0", base, "--", "*.java"],
            capture_output=True, text=True, check=True,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as e:
        return [{"file": str(repo), "line": 0, "kind": "diff_unavailable", "snippet": str(e)[:160]}]

    findings: list[dict] = []
    cur = None
    counts: dict[str, list] = {}
    for line in out.splitlines():
        if line.startswith("+++ b/"):
            cur = line[6:]
            counts.setdefault(cur, [0, 0, []])
            continue
        if cur is None or not _ADDED_CODE.match(line):
            continue
        body = line[1:]
        if _ADDED_COMMENT.match(line):
            counts[cur][0] += 1
            counts[cur][2].append(body.strip())
        elif body.strip():
            counts[cur][1] += 1

    for f, (ncom, ncode, samples) in sorted(counts.items()):
        if ncom > MAX_ADDED_COMMENT_LINES:
            findings.append({
                "file": f,
                "line": 0,
                "kind": "added_comment_volume",
                "snippet": f"{ncom} comment lines added over {ncode} code lines "
                           f"(max {MAX_ADDED_COMMENT_LINES}) — e.g. {samples[0][:80]}",
            })
    return findings


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
    ap.add_argument("--diff", metavar="BASE", help="count comment lines added vs BASE (per repo)")
    ap.add_argument("--repo", default=".", help="repo dir for --diff")
    args = ap.parse_args(argv)

    if args.diff:
        repo = Path(args.repo)
        if not repo.is_absolute():
            repo = (ROOT / repo).resolve()
        findings = diff_findings(repo, args.diff)
        if args.json:
            print(json.dumps({"findings": findings}, indent=2))
        elif findings:
            print(f"java-comment-lint FAIL: {len(findings)} finding(s) vs {args.diff}", file=sys.stderr)
            for f in findings:
                print(f"  {f['file']} [{f['kind']}] {f['snippet']}", file=sys.stderr)
            print("Default to ZERO comments (cursor-bundle/memory/feedback_keep_code_simple.md RULE 1). "
                  "Rationale belongs in the commit message and .cursor/changelog.md, not inline.",
                  file=sys.stderr)
            return 1
        else:
            print(f"java-comment-lint PASS (diff vs {args.diff})")
        return 0

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
