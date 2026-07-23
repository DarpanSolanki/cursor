#!/usr/bin/env python3
"""
build_curated.py — fold hand-authored CURATED overlays into the KG.

Reads cursor-bundle/kg/curated/*.jsonl (via _paths). Also folds promoted
learnings written by learning_bus.compact_bus → curated/promoted_learnings.jsonl.

Usage: build_curated.py
"""
import os, sys, json, glob
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import CURATED

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

if not CURATED.is_dir():
    sys.exit(0)

for path in sorted(CURATED.glob("*.jsonl")):
    for ln, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"build_curated: skip {path.name}:{ln} — bad JSON ({e})\n")
            continue
        t = o.get("t")
        if t == "node" and o.get("id") and o.get("kind"):
            emit(o)
        elif t == "edge" and o.get("from") and o.get("to") and o.get("rel"):
            emit(o)
        else:
            sys.stderr.write(f"build_curated: skip {path.name}:{ln} — missing fields\n")
