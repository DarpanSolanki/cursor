#!/usr/bin/env python3
"""kg_after_edit — fail-closed freshness + best-effort single-file reindex.

Supported shapes (extractor-aligned):
  - orchestration XML (*_orc.xml / orchestration/*.xml with <Request>)
  - JPA @Table Java under src/main/java
  - *Processor.java / *Writer.java under src/main/java

Unsupported → set .pending-kg-rebuild + leave STALE (no bogus patch).
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from _paths import WORKSPACE, KG_DATA  # noqa: E402

PENDING = WORKSPACE / ".cursor" / ".pending-kg-rebuild"
DB = KG_DATA / "kg.db"
TABLE_RE = re.compile(r'@Table\(\s*name\s*=\s*"([^"]+)"')
CLASS_RE = re.compile(r"\b(?:public\s+)?class\s+(\w+)")
PROC_BEAN_RE = re.compile(r'<Processor\s+[^>]*\bbean\s*=\s*"([^"]+)"')
REQ_RE = re.compile(r'<Request\s+[^>]*\bname\s*=\s*"([^"]+)"')


def _flag_pending(reason: str) -> None:
    PENDING.parent.mkdir(parents=True, exist_ok=True)
    PENDING.write_text(
        time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()) + f" {reason}\n",
        encoding="utf-8",
    )


def _classify(rel: str) -> str:
    r = rel.replace("\\", "/")
    if "/build/" in r or "/.git/" in r:
        return "ignore"
    if r.endswith(".xml") and ("orchestration" in r or r.endswith("_orc.xml")):
        return "orch"
    if r.endswith(".java") and "/src/main/java/" in r:
        if r.endswith("Processor.java") or r.endswith("Writer.java") or r.endswith("ItemWriter.java"):
            return "processor_java"
        try:
            txt = (WORKSPACE / r).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return "unsupported"
        if "@Table" in txt and TABLE_RE.search(txt):
            return "table_java"
        return "unsupported"
    return "unsupported"


def _patch_processor_java(rel: str, db: sqlite3.Connection) -> str:
    path = WORKSPACE / rel
    txt = path.read_text(encoding="utf-8", errors="replace")
    m = CLASS_RE.search(txt)
    if not m:
        _flag_pending(f"processor_java_no_class:{rel}")
        return "STALE pending (no class)"
    cls = m.group(1)
    bean = cls[0].lower() + cls[1:] if cls[0].isupper() else cls
    nid = f"processor:{bean}"
    row = db.execute("SELECT id, json FROM nodes WHERE id=?", (nid,)).fetchone()
    note = f"incremental:{int(time.time())}"
    if row:
        try:
            o = json.loads(row[1] or "{}")
        except json.JSONDecodeError:
            o = {"t": "node", "id": nid, "kind": "processor", "label": bean}
        o["src"] = f"{rel}:1"
        o["note"] = note
        db.execute(
            "UPDATE nodes SET src=?, json=? WHERE id=?",
            (f"{rel}:1", json.dumps(o, ensure_ascii=False), nid),
        )
    else:
        o = {
            "t": "node",
            "id": nid,
            "kind": "processor",
            "label": bean,
            "src": f"{rel}:1",
            "note": note,
            "role": "incremental",
        }
        db.execute(
            "INSERT OR REPLACE INTO nodes(id,kind,label,repo,role,src,json) VALUES(?,?,?,?,?,?,?)",
            (nid, "processor", bean, "", "incremental", f"{rel}:1", json.dumps(o, ensure_ascii=False)),
        )
        db.execute(
            "INSERT INTO node_fts(id,kind,text) VALUES(?,?,?)",
            (nid, "processor", f"{nid} {bean}"),
        )
    db.commit()
    return f"UPDATED {nid} note={note}"


def _patch_table_java(rel: str, db: sqlite3.Connection) -> str:
    path = WORKSPACE / rel
    txt = path.read_text(encoding="utf-8", errors="replace")
    updated = []
    for m in TABLE_RE.finditer(txt):
        tbl = m.group(1)
        tid = f"table:{tbl}"
        o = {
            "t": "node",
            "id": tid,
            "kind": "table",
            "label": tbl,
            "src": rel,
            "note": f"incremental:{int(time.time())}",
        }
        db.execute(
            "INSERT OR REPLACE INTO nodes(id,kind,label,repo,role,src,json) VALUES(?,?,?,?,?,?,?)",
            (tid, "table", tbl, "", None, rel, json.dumps(o, ensure_ascii=False)),
        )
        db.execute("DELETE FROM node_fts WHERE id=?", (tid,))
        db.execute("INSERT INTO node_fts(id,kind,text) VALUES(?,?,?)", (tid, "table", f"{tid} {tbl}"))
        updated.append(tid)
    db.commit()
    return f"UPSERT tables {updated}"


def _patch_orch(rel: str, db: sqlite3.Connection) -> str:
    # Best-effort: re-emit processor nodes for beans in this file; requests left to full rebuild.
    # Full request chain rewrite is gnarly (seq/cond) — flag pending for orch, still touch beans.
    path = WORKSPACE / rel
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    beans = []
    for i, line in enumerate(lines, 1):
        m = PROC_BEAN_RE.search(line)
        if m:
            bean = m.group(1)
            beans.append((bean, i))
            nid = f"processor:{bean}"
            o = {
                "t": "node",
                "id": nid,
                "kind": "processor",
                "label": bean,
                "src": f"{rel}:{i}",
                "note": f"incremental_orch:{int(time.time())}",
            }
            db.execute(
                "INSERT OR REPLACE INTO nodes(id,kind,label,repo,role,src,json) VALUES(?,?,?,?,?,?,?)",
                (nid, "processor", bean, "", None, f"{rel}:{i}", json.dumps(o, ensure_ascii=False)),
            )
    # Orch request spine needs full rebuild for correct seq — fail-closed pending
    _flag_pending(f"orch_partial:{rel}")
    db.commit()
    return f"ORCH_PARTIAL beans={len(beans)} pending_full_rebuild"


def main(argv: list[str]) -> int:
    if len(argv) < 1:
        print("usage: kg_after_edit.py <rel-or-abs-path>")
        return 2
    raw = argv[0]
    p = Path(raw)
    if not p.is_absolute():
        p = WORKSPACE / raw
    try:
        rel = str(p.resolve().relative_to(WORKSPACE.resolve()))
    except ValueError:
        print(f"SKIP outside workspace: {raw}")
        return 0
    kind = _classify(rel)
    t0 = time.perf_counter()
    if kind == "ignore":
        print(f"IGNORE {rel}")
        return 0
    if kind == "unsupported":
        _flag_pending(f"unsupported:{rel}")
        ms = (time.perf_counter() - t0) * 1000
        print(f"STALE_FLAG unsupported shape {rel} pending-kg-rebuild ({ms:.0f}ms)")
        return 0
    if not DB.is_file():
        _flag_pending(f"no_db:{rel}")
        print("STALE_FLAG no kg.db")
        return 0
    db = sqlite3.connect(str(DB))
    if kind == "processor_java":
        msg = _patch_processor_java(rel, db)
    elif kind == "table_java":
        msg = _patch_table_java(rel, db)
    else:
        msg = _patch_orch(rel, db)
    ms = (time.perf_counter() - t0) * 1000
    print(f"OK {kind} {rel} {msg} wall_ms={ms:.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
