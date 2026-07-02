#!/usr/bin/env python3
"""Write cache manifest JSON for a composite KG key."""
import json
import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))
from _paths import KG_DATA
from kg_composite import snapshot


def write_manifest(key: str, path: Path | None = None) -> dict:
    path = path or (KG_DATA / "cache" / f"{key}.manifest.json")
    snap = snapshot()
    stats = {}
    sf = KG_DATA / "stats.json"
    if sf.is_file():
        stats = json.loads(sf.read_text(encoding="utf-8"))
    wm = stats.get("watermark", {})
    m = {
        "key": key,
        "built_at": wm.get("built_at") or stats.get("built_at"),
        "nodes": stats.get("nodes"),
        "edges": stats.get("edges"),
        "composite": snap["composite"],
        "repos": {
            r: {
                "branch": v["branch"],
                "sha": (v["sha"] or "")[:10],
                "dirty": v.get("dirty", False),
                "provisional": v.get("provisional", False),
            }
            for r, v in snap["repos"].items()
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(m, indent=2), encoding="utf-8")
    return m


def main():
    key = sys.argv[1] if len(sys.argv) > 1 else None
    if not key:
        from kg_composite import composite_key
        key = composite_key()
    write_manifest(key)
    print(key)


if __name__ == "__main__":
    main()
