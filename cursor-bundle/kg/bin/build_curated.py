#!/usr/bin/env python3
"""
build_curated.py — fold hand-authored CURATED overlays into the KG.

Most of the graph is auto-extracted from code (orchestration, data-access) and
brain docs. But some knowledge is NOT mechanically derivable — chiefly
CONFIG-RESOLUTION dependencies: "this amount/field is computed by a resolver that
looks up a master/price-setup mapping, and silently becomes 0 when that mapping is
missing/inactive." That is the "amount shows zero / charge not displaying" bug
class. Capturing it as `config` nodes + `resolves_config`/`reads_config` edges lets
`kg config <flow>` answer "what config does this amount depend on, and how does it
fail to 0" BEFORE anyone greps code.

This builder just validates and passes through every JSON object in
claude/kg/curated/*.jsonl (same node/edge schema as the other builders). To add a
new curated dependency: append a line to a *.jsonl there and rebuild. New knowledge
plugs into the graph — no loose markdown island.

Usage: build_curated.py            (no args; reads claude/kg/curated/*.jsonl)
"""
import os, sys, json, glob

ROOT = "/home/darpan/darpan"
CURATED = os.path.join(ROOT, "claude", "kg", "curated")

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

if not os.path.isdir(CURATED):
    sys.exit(0)

for path in sorted(glob.glob(os.path.join(CURATED, "*.jsonl"))):
    for ln, line in enumerate(open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError as e:
            sys.stderr.write(f"build_curated: skip {os.path.basename(path)}:{ln} — bad JSON ({e})\n")
            continue
        t = o.get("t")
        if t == "node" and o.get("id") and o.get("kind"):
            emit(o)
        elif t == "edge" and o.get("from") and o.get("to") and o.get("rel"):
            emit(o)
        else:
            sys.stderr.write(f"build_curated: skip {os.path.basename(path)}:{ln} — missing fields\n")
