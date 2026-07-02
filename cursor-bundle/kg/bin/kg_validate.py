#!/usr/bin/env python3
"""Validate kg.db + stats.json integrity (corruption guard). Exit 0=ok, 1=fail."""
import json
import sqlite3
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import KG_DATA
from kg_composite import composite_key, snapshot

DB = KG_DATA / "kg.db"
STATS = KG_DATA / "stats.json"
MIN_NODES = 3000
MIN_EDGES = 10000


def fail(msg: str) -> None:
    print(f"INVALID: {msg}", file=sys.stderr)
    sys.exit(1)


def main():
    if not DB.is_file():
        fail(f"missing {DB}")
    if DB.stat().st_size < 100_000:
        fail(f"kg.db too small ({DB.stat().st_size} bytes)")

    try:
        c = sqlite3.connect(str(DB))
        ok = c.execute("PRAGMA integrity_check").fetchone()[0]
        if ok != "ok":
            fail(f"sqlite integrity_check: {ok}")
        n = c.execute("SELECT count(*) FROM nodes").fetchone()[0]
        e = c.execute("SELECT count(*) FROM edges").fetchone()[0]
        if n < MIN_NODES:
            fail(f"node count {n} < {MIN_NODES}")
        if e < MIN_EDGES:
            fail(f"edge count {e} < {MIN_EDGES}")
        c.execute("SELECT 1 FROM node_fts WHERE node_fts MATCH 'disburseLoan*' LIMIT 1").fetchone()
        c.close()
    except Exception as ex:
        fail(str(ex))

    if STATS.is_file():
        try:
            stats = json.loads(STATS.read_text(encoding="utf-8"))
            sn = stats.get("nodes", 0)
            if sn and abs(sn - n) > max(50, sn * 0.05):
                fail(f"stats.json nodes {sn} vs db nodes {n} mismatch")
        except Exception as ex:
            fail(f"stats.json: {ex}")

    manifest = KG_DATA / "cache" / f"{composite_key()}.manifest.json"
    if manifest.is_file():
        try:
            m = json.loads(manifest.read_text(encoding="utf-8"))
            live = composite_key()
            if m.get("key") != live:
                print(f"WARN: active kg.db key {live} != manifest {m.get('key')} (branch-set moved)", file=sys.stderr)
        except Exception:
            pass

    print(f"OK: {n} nodes, {e} edges, integrity_check passed")
    if "--json" in sys.argv:
        print(json.dumps({"nodes": n, "edges": e, "key": composite_key()}))


if __name__ == "__main__":
    main()
