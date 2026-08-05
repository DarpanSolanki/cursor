#!/usr/bin/env python3
"""
build_tables.py — fold the platform data model into the one graph.

For every @Table(name="...") JPA entity across all repos, emit a `table` node and
an `owns` edge repo->table (the service that owns the entity). Deterministic grep-
style scan, stdlib only. stdout = JSONL.

Usage: build_tables.py <repoDir> [<repoDir> ...]
"""
import os, re, sys, glob

TABLE_RE = re.compile(r'@Table\(\s*name\s*=\s*"([^"]+)"')
ENTITY_RE = re.compile(r'\bclass\s+(\w+)')

def emit(o): sys.stdout.write(__import__("json").dumps(o, ensure_ascii=False) + "\n")

def repo_name(p):
    for seg in os.path.abspath(p).split(os.sep):
        if seg.startswith("novopay-") or seg.startswith("trustt-"): return seg
    return os.path.basename(p.rstrip(os.sep))

seen=set()
# `novopay-platform-lib` is a symlink to `trustt-platform-lib` — build_config.json
# declares it an alias "covered once under trustt-platform-lib". Scanning both
# double-owns every lib table, and the alias sorts first so it would win the name.
_real_targets={os.path.realpath(d) for d in sys.argv[1:] if not os.path.islink(d.rstrip(os.sep))}
for repo_dir in sys.argv[1:]:
    if os.path.islink(repo_dir.rstrip(os.sep)) and os.path.realpath(repo_dir) in _real_targets:
        continue
    repo=repo_name(repo_dir)
    # trustt-platform-lib is a composite build: sources live in infra-*/src/main/java,
    # never repo/src/main/java. Assuming the single-module layout hid its entities
    # (platform_master tenant/service/api master) from the KG completely.
    java_files = glob.glob(os.path.join(repo_dir,"src","main","java","**","*.java"), recursive=True)
    if not java_files:
        java_files = glob.glob(os.path.join(repo_dir,"*","src","main","java","**","*.java"), recursive=True)
    for jf in java_files:
        try:
            txt=open(jf,encoding="utf-8",errors="replace").read()
        except OSError: continue
        if "@Table" not in txt: continue
        rel=os.path.relpath(jf, start=os.getcwd())
        for m in TABLE_RE.finditer(txt):
            tbl=m.group(1)
            tid=f"table:{tbl}"
            # entity class name following the annotation (best-effort)
            ent=ENTITY_RE.search(txt, m.end())
            if tid not in seen:
                seen.add(tid)
                emit({"t":"node","id":tid,"kind":"table","label":tbl,"repo":repo,
                      "entity":ent.group(1) if ent else None,"src":f"{rel}"})
            emit({"t":"edge","from":f"service:{repo}","to":tid,"rel":"owns",
                  "note":ent.group(1) if ent else "","src":rel})
