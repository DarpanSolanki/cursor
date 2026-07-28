#!/usr/bin/env python3
"""Doctor: change_test_map class_to_api vs KG processor→request edges (C1)."""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "scripts/lib/change_test_map.json"
KG_DB = ROOT / "cursor-bundle/kg/data/kg.db"


def main() -> int:
    if not MAP.is_file():
        print("FAIL: change_test_map.json missing")
        return 1
    data = json.loads(MAP.read_text(encoding="utf-8"))
    class_map = data.get("class_to_api") or {}
    if not KG_DB.is_file():
        print("WARN: KG missing — skip drift check (NOT VERIFIED)")
        return 0
    conn = sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    drift: list[str] = []
    ok = 0
    for stem, api in sorted(class_map.items()):
        bean = stem[0].lower() + stem[1:] if stem.endswith("Processor") else ""
        if not bean:
            ok += 1
            continue
        pid = f"processor:{bean}"
        rows = conn.execute(
            "SELECT src_id FROM edges WHERE dst_id=? AND src_id LIKE 'request:%' AND rel='invokes'",
            (pid,),
        ).fetchall()
        kg_apis = {r[0].rsplit("/", 1)[-1] if "/" in r[0] else r[0].split(":", 1)[-1] for r in rows}
        if kg_apis and api not in kg_apis:
            drift.append(f"{stem}: map={api} kg={sorted(kg_apis)}")
        else:
            ok += 1
    conn.close()
    print(f"mapping-vs-KG: checked={len(class_map)} ok={ok} drift={len(drift)}")
    for d in drift[:20]:
        print(f"  DRIFT {d}")
    return 1 if drift else 0


if __name__ == "__main__":
    sys.exit(main())
