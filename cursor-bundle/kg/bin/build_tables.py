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
for repo_dir in sys.argv[1:]:
    repo=repo_name(repo_dir)
    for jf in glob.glob(os.path.join(repo_dir,"src","main","java","**","*.java"), recursive=True):
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
