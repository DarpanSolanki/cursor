#!/usr/bin/env python3
"""
build_db.py — materialize kg.jsonl into kg.db (full) or incremental case/error upsert.

Usage:
  build_db.py <kg.jsonl> <kg.db>
  build_db.py --incremental-cases <kg.jsonl> <kg.db>
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

SCHEMA = """
CREATE TABLE IF NOT EXISTS nodes(id TEXT PRIMARY KEY, kind TEXT, label TEXT, repo TEXT, role TEXT, src TEXT, json TEXT);
CREATE TABLE IF NOT EXISTS edges(src_id TEXT, dst_id TEXT, rel TEXT, seq INTEGER, cond TEXT, note TEXT, src TEXT, json TEXT);
CREATE INDEX IF NOT EXISTS ix_edges_src ON edges(src_id, rel);
CREATE INDEX IF NOT EXISTS ix_edges_dst ON edges(dst_id, rel);
CREATE INDEX IF NOT EXISTS ix_nodes_kind ON nodes(kind);
CREATE VIRTUAL TABLE IF NOT EXISTS node_fts USING fts5(id UNINDEXED, kind UNINDEXED, text);
"""


def _is_case_node(o: dict) -> bool:
    return o.get("kind") in ("case", "error")


def _is_case_edge(o: dict) -> bool:
    fr, to = o.get("from", ""), o.get("to", "")
    return fr.startswith("case:") or fr.startswith("error:") or to.startswith("case:") or to.startswith("error:")


def full_build(src: str, dbpath: str) -> None:
    if os.path.exists(dbpath):
        os.remove(dbpath)
    db = sqlite3.connect(dbpath)
    db.executescript(SCHEMA)
    nrows, erows, frows = [], [], []
    for line in open(src, encoding="utf-8"):
        o = json.loads(line)
        if o["t"] == "node":
            nrows.append(
                (
                    o["id"],
                    o.get("kind"),
                    o.get("label"),
                    o.get("repo"),
                    o.get("role"),
                    o.get("src"),
                    json.dumps(o, ensure_ascii=False),
                )
            )
            frows.append(
                (
                    o["id"],
                    o.get("kind"),
                    " ".join(str(o.get(k, "")) for k in ("id", "label", "role", "repo")),
                )
            )
        else:
            erows.append(
                (
                    o["from"],
                    o["to"],
                    o.get("rel"),
                    o.get("seq"),
                    o.get("cond"),
                    o.get("note"),
                    o.get("src"),
                    json.dumps(o, ensure_ascii=False),
                )
            )
    db.executemany("INSERT OR IGNORE INTO nodes VALUES(?,?,?,?,?,?,?)", nrows)
    db.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)", erows)
    db.executemany("INSERT INTO node_fts VALUES(?,?,?)", frows)
    db.commit()
    n = db.execute("SELECT count(*) FROM nodes").fetchone()[0]
    e = db.execute("SELECT count(*) FROM edges").fetchone()[0]
    db.close()
    print(f"  kg.db: {n} nodes, {e} edges (indexed + FTS5)")


def incremental_cases(src: str, dbpath: str) -> None:
    if not os.path.exists(dbpath):
        full_build(src, dbpath)
        print("  (incremental-cases: no db — full build)")
        return

    db = sqlite3.connect(dbpath)
    db.executescript(SCHEMA)
    ids = [r[0] for r in db.execute("SELECT id FROM nodes WHERE kind IN ('case','error')").fetchall()]
    if ids:
        placeholders = ",".join("?" * len(ids))
        db.execute(f"DELETE FROM node_fts WHERE id IN ({placeholders})", ids)
    db.execute("DELETE FROM edges WHERE src_id LIKE 'case:%' OR src_id LIKE 'error:%' OR dst_id LIKE 'case:%' OR dst_id LIKE 'error:%'")
    db.execute("DELETE FROM nodes WHERE kind IN ('case', 'error')")

    nrows, erows, frows = [], [], []
    for line in open(src, encoding="utf-8"):
        o = json.loads(line)
        if o["t"] == "node" and _is_case_node(o):
            nrows.append(
                (
                    o["id"],
                    o.get("kind"),
                    o.get("label"),
                    o.get("repo"),
                    o.get("role"),
                    o.get("src"),
                    json.dumps(o, ensure_ascii=False),
                )
            )
            frows.append(
                (
                    o["id"],
                    o.get("kind"),
                    " ".join(str(o.get(k, "")) for k in ("id", "label", "role", "repo")),
                )
            )
        elif o["t"] != "node" and _is_case_edge(o):
            erows.append(
                (
                    o["from"],
                    o["to"],
                    o.get("rel"),
                    o.get("seq"),
                    o.get("cond"),
                    o.get("note"),
                    o.get("src"),
                    json.dumps(o, ensure_ascii=False),
                )
            )

    db.executemany("INSERT OR REPLACE INTO nodes VALUES(?,?,?,?,?,?,?)", nrows)
    db.executemany("INSERT INTO edges VALUES(?,?,?,?,?,?,?,?)", erows)
    db.executemany("INSERT INTO node_fts VALUES(?,?,?)", frows)
    db.commit()
    n = db.execute("SELECT count(*) FROM nodes WHERE kind IN ('case','error')").fetchone()[0]
    e = db.execute(
        "SELECT count(*) FROM edges WHERE src_id LIKE 'case:%' OR dst_id LIKE 'error:%'"
    ).fetchone()[0]
    db.close()
    print(f"  kg.db cases incremental: {len(nrows)} case/error nodes, {len(erows)} edges (db has {n} cases, {e} case edges)")


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--incremental-cases"]
    incremental = "--incremental-cases" in sys.argv
    if len(args) != 2:
        print("Usage: build_db.py [--incremental-cases] <kg.jsonl> <kg.db>", file=sys.stderr)
        return 2
    src, dbpath = args
    if incremental:
        incremental_cases(src, dbpath)
    else:
        full_build(src, dbpath)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
