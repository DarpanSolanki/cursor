"""Term → workspace-knowledge index, so a search can be answered before it runs.

`.cursor/kg-grep-leak.jsonl` had 999 entries: every time an agent grepped a service tree
instead of reading knowledge that already existed. The hook that wrote it only counted.
Nothing told the agent "this is already documented" — so correct, curated knowledge
(redis-key-registry, gaps, rules, memory) was rediscovered by reading source line by line.

Three layers, all answered from one file in milliseconds:

  docs     every knowledge markdown under .cursor, cursor-bundle/brain, memory,
           system_brain and docs — recursively. The first version globbed one level,
           so .cursor/skills/** and the whole brain were unreachable.
  scripts  script path + module docstring terms, so "is there already a script for X"
           is answerable without listing scripts/.
  kg       node labels from kg.db, answered as the kg command that resolves them plus
           the file:line. A class name should never send anyone to grep for its file.

    python3 scripts/lib/knowledge_index.py build
    python3 scripts/lib/knowledge_index.py ask notification_message
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / ".cursor/.knowledge-term-index.json"
KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"

DOC_SOURCES = [".cursor", "cursor-bundle/memory", "cursor-bundle/brain", "system_brain", "docs"]
SCRIPT_SOURCES = ["scripts/bin", "scripts/lib", "scripts/testing", "cursor-bundle/kg/bin"]
SKIP_NAMES = {"changelog.md", "kg-grep-leak.jsonl"}
SKIP_DIRS = {"node_modules", "__pycache__", ".git", "scratch"}

TERM = re.compile(r"[A-Za-z_][A-Za-z0-9_]{5,}")
STOP = {
    "workspace", "accounting", "platform", "trustt", "novopay", "should", "before",
    "because", "through", "between", "without", "million", "example", "details",
    "changed", "already", "against", "process", "service", "request", "response",
    "message", "default", "current", "problem", "instead",
}
KG_CMD = {
    "symbol": "kg impact", "processor": "kg impact", "request": "kg flow",
    "table": "kg writes", "error": "kg error", "topic": "kg node",
    "scheduler": "kg node", "entity": "kg node", "redis_key": "kg node",
}
MAX_REFS = 4


def _walk(rel: str, suffix: str) -> list[Path]:
    base = ROOT / rel
    if not base.is_dir():
        return []
    return [
        p for p in base.rglob(f"*{suffix}")
        if p.name not in SKIP_NAMES and not SKIP_DIRS & set(p.parts)
    ]


def _files() -> list[Path]:
    out: list[Path] = []
    for rel in DOC_SOURCES:
        out.extend(_walk(rel, ".md"))
    return sorted(set(out))


def _add(index: dict, term: str, ref: str) -> None:
    term = term.lower()
    if term in STOP or len(term) > 48:
        return
    bucket = index.setdefault(term, [])
    if len(bucket) < MAX_REFS and ref not in bucket:
        bucket.append(ref)


def _index_docs(index: dict) -> int:
    files = _files()
    for path in files:
        rel = str(path.relative_to(ROOT))
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            continue
        for n, line in enumerate(lines, 1):
            if len(line) < 12:
                continue
            for raw in TERM.findall(line):
                _add(index, raw, f"{rel}:{n}")
    return len(files)


def _index_scripts(index: dict) -> int:
    seen = 0
    for rel in SCRIPT_SOURCES:
        for path in _walk(rel, ".py") + _walk(rel, ".sh"):
            seen += 1
            ref = str(path.relative_to(ROOT))
            head = []
            try:
                with path.open(errors="replace") as fh:
                    for i, line in enumerate(fh):
                        if i > 25:
                            break
                        head.append(line)
            except OSError:
                continue
            for raw in TERM.findall(path.stem + " " + "".join(head)):
                _add(index, raw, ref)
    return seen


def _index_kg(index: dict) -> int:
    if not KG_DB.is_file():
        return 0
    try:
        con = sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    except sqlite3.Error:
        return 0
    n = 0
    with con:
        for kind, label, src in con.execute(
            "SELECT kind,label,src FROM nodes WHERE label IS NOT NULL AND kind IN "
            "('symbol','processor','request','table','error','topic','scheduler','entity','redis_key')"
        ):
            cmd = KG_CMD.get(kind)
            if not cmd:
                continue
            bare = label.split("#")[0].split("(")[0].strip()
            if len(bare) < 6:
                continue
            ref = f"{cmd} {bare}" + (f"  [{src}]" if src else "")
            _add(index, bare, ref)
            n += 1
    con.close()
    return n


def build() -> dict:
    index: dict[str, list[str]] = {}
    docs = _index_docs(index)
    scripts = _index_scripts(index)
    nodes = _index_kg(index)
    INDEX.write_text(json.dumps(index, separators=(",", ":")))
    build.stats = {"docs": docs, "scripts": scripts, "kg_nodes": nodes, "terms": len(index)}
    return index


def load() -> dict:
    if not INDEX.is_file():
        return build()
    try:
        return json.loads(INDEX.read_text())
    except json.JSONDecodeError:
        return build()


def ask(terms: list[str], limit: int = 3) -> list[tuple[str, list[str]]]:
    index = load()
    hits: list[tuple[str, list[str]]] = []
    for raw in terms:
        term = raw.lower().strip("\"'`*.,;|()[]{}")
        if len(term) < 6 or term in STOP:
            continue
        found = index.get(term)
        if found:
            hits.append((term, found))
        if len(hits) >= limit:
            break
    return hits


def terms_from_command(cmd: str) -> list[str]:
    return TERM.findall(cmd)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build")
    a = sub.add_parser("ask")
    a.add_argument("terms", nargs="+")
    c = sub.add_parser("from-command")
    c.add_argument("command")
    args = ap.parse_args(argv)

    if args.cmd == "build":
        build()
        s = build.stats
        print(f"indexed {s['terms']} terms — {s['docs']} docs, {s['scripts']} scripts, "
              f"{s['kg_nodes']} kg nodes -> {INDEX.relative_to(ROOT)}")
        return 0

    terms = args.terms if args.cmd == "ask" else terms_from_command(args.command)
    hits = ask(terms)
    if not hits:
        return 1
    for term, refs in hits:
        print(f"{term}: {', '.join(refs)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
