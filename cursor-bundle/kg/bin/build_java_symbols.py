#!/usr/bin/env python3
"""
build_java_symbols.py — index Java methods as symbol nodes for kg impact.

Branch-correct: scans live checkout of each repo passed on the CLI.
Keeps volume bounded: money-path packages only; skips trivial getters/setters.

Usage: build_java_symbols.py <repoDir> [<repoDir> ...]
Emits JSONL node/edge lines to stdout (append into KG raw build).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Paths that matter for loan/money impact analysis (relative under src/main/java)
_PKG_HIT = re.compile(
    r"/(batchnew|loan|interest|foreclosure|deathforeclosure|grouploan|"
    r"transaction|repayment|prepayment|dpi|penal|npa|generalledger)/"
)
_CLASS_RE = re.compile(
    r"(?:public\s+|protected\s+|private\s+)?(?:abstract\s+|final\s+|static\s+)*"
    r"(?:class|interface|enum)\s+(\w+)"
)
_METHOD_RE = re.compile(
    r"(?:public|protected|private)\s+(?:static\s+)?(?:final\s+)?"
    r"[\w.<>,\[\]?]+\s+(\w+)\s*\("
)
_SKIP_METHOD = re.compile(
    r"^(get|set|is|has|toString|hashCode|equals|canEqual|builder|build|"
    r"valueOf|values|ordinal|name|compareTo)$"
)


def _emit_node(nid: str, **kw) -> None:
    o = {"t": "node", "id": nid, **kw}
    print(json.dumps(o, ensure_ascii=False))


def _emit_edge(frm: str, to: str, rel: str, **kw) -> None:
    print(json.dumps({"t": "edge", "from": frm, "to": to, "rel": rel, **kw}, ensure_ascii=False))


def _scan_repo(repo: Path) -> int:
    root = repo / "src" / "main" / "java"
    if not root.is_dir():
        return 0
    n = 0
    svc = f"service:{repo.name}"
    for java in root.rglob("*.java"):
        rel = str(java.relative_to(repo)).replace("\\", "/")
        if not _PKG_HIT.search("/" + rel):
            continue
        try:
            text = java.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        cm = _CLASS_RE.search(text)
        if not cm:
            continue
        cls = cm.group(1)
        for m in _METHOD_RE.finditer(text):
            method = m.group(1)
            if _SKIP_METHOD.match(method) or method == cls:
                continue
            line = text.count("\n", 0, m.start()) + 1
            nid = f"symbol:{repo.name}/{cls}#{method}"
            label = f"{cls}#{method}"
            src = f"{repo.name}/{rel}:{line}"
            _emit_node(
                nid,
                kind="symbol",
                label=label,
                role=f"java method {cls}.{method} {method}",
                repo=repo.name,
                src=src,
            )
            _emit_edge(svc, nid, "defines", src=src)
            # Spring bean name ≈ lower-camel class; link only Processor* (orch beans exist)
            if cls.endswith("Processor"):
                bean = cls[0].lower() + cls[1:]
                _emit_edge(f"processor:{bean}", nid, "implements", note="java method", src=src)
            n += 1
    return n


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: build_java_symbols.py <repoDir> ...", file=sys.stderr)
        sys.exit(2)
    total = 0
    for name in sys.argv[1:]:
        p = Path(name)
        if not p.is_dir():
            continue
        total += _scan_repo(p)
    print(f"# build_java_symbols: {total} symbol nodes", file=sys.stderr)


if __name__ == "__main__":
    main()
