#!/usr/bin/env python3
"""
kg.py — query the self-contained system knowledge graph.

Backed by a real SQLite store (claude/kg/data/kg.db): indexed nodes/edges +
FTS5 search + recursive-CTE traversal. Stdlib only, in-folder, no external dep.
Every answer prints `src` provenance (file:line) so it is verifiable.

Commands:
  stats                          graph size + breakdown
  search <text>                  full-text node search (FTS5)
  node <id>                      a node + its in/out edges (with provenance)
  flow <request>                 ordered processor chain of a Request (the flow spine) + DB footprint
  crud <request>                 full DB footprint of a flow: per-processor reads/writes/deletes + read-set/write-set
  reads | writes | deletes <table>   reverse: which processors/flows read | write | delete a table
  deps <service>                 what a service calls / is called by
  docs <id>                      knowledge docs that document/mention a node
  neighbors <id> [--rel R] [--in|--out]
  impact <id> [--depth N]        reverse blast radius (who reaches <id>) via recursive CTE
  path <a> <b> [--depth N]       shortest directed path a->b via recursive CTE
  cases [<flow/table>]           PRECEDENT — shipped fixes (CHANGELOG); per-node = "fixed this before?"
  fixed-elsewhere <query> [--repo R] [--base B]
                                  verified higher-branch fixes + file-touch candidates (read-only)
  table <name>                   a table: owning repo + entity + cases that touched it + docs
  error <code>                   cases that hit an error code (who hit it, fix SHA)
  why [<request/processor/table/symptom>]   FAILURE-MODE catalog — the silent decision-points where bugs hide (wrong/zero/null/empty/missing/reverted). `kg why <request>` = the whole flow's silent surface. The 'pinpoint any issue' entrypoint.
  doctor                         health + freshness + branch-watermark drift (sources newer than kg.db, repo moved off built branch)
  watermark                      per-repo branch@sha the knowledge was built from vs live HEAD ("knowledge current up to which branch")
  fresh                          one-line verdict: is the KG branch-correct for the current live checkout? (used at session start)
  validate                       KG integrity + min nodes/edges check (exit 1 on fail; MCP: kg_validate)
  orient <request>               LOOKUP entry — flow spine + why/silent branches + cases (MCP: kg_orient)
  stale [<doc>]                  brain docs that cite repo files which no longer exist (drift vs code)
  sql "<SELECT ...>"             arbitrary read-only SQL over nodes/edges (power users)
Node ids are typed: request:  processor:  service:  api:  doc:  table:  case:  error:  diag:
Partial ids resolve when unambiguous (e.g. `flow disburseLoan`, `deps accounting`).
"""
import os, sys, sqlite3

HERE = os.path.dirname(__file__)
sys.path.insert(0, HERE)
try:
    from _paths import WORKSPACE as _WS, KG_DATA as _KG_DATA
    ROOT = str(_WS)
    DB = str(_KG_DATA / "kg.db")
except Exception:
    ROOT = os.path.abspath(os.path.join(HERE, "../../.."))
    DB = os.path.join(HERE, "..", "data", "kg.db")

_KG_EXTS = (".java", ".xml")
_KG_PATH_HINTS = ("/src/", "src/", "orchestration", "deploy/", "messagebroker")

def conn(readonly=False):
    if not os.path.exists(DB):
        sys.exit("kg.db missing — run claude/kg/bin/build.sh first")
    if readonly:
        uri = f"file:{DB}?mode=ro"
        c = sqlite3.connect(uri, uri=True)
    else:
        c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c

def resolve(c, q):
    """Resolve a node id. Requests are repo-scoped (request:{repo}/{name}); bare
    names resolve by unique label. Use repo/name when ambiguous."""
    if c.execute("SELECT 1 FROM nodes WHERE id=?", (q,)).fetchone():
        return q
    for pref in ("request:", "service:", "processor:", "api:", "doc:", "topic:", "scheduler:", "table:"):
        if c.execute("SELECT 1 FROM nodes WHERE id=?", (pref + q,)).fetchone():
            return pref + q
    # request by label (Upgrade 10 repo-scope)
    if "/" not in q and not q.startswith("request:"):
        hits = [r[0] for r in c.execute(
            "SELECT id FROM nodes WHERE kind='request' AND label=?", (q,)
        ).fetchall()]
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            sys.stderr.write(f"ambiguous 'request:{q}' -> {hits[:12]}{' ...' if len(hits) > 12 else ''}\n")
            sys.stderr.write("  hint: use <repo>/<name> e.g. trustt-platform-api-gateway/deleteUser\n")
            return None
    # repo/name shorthand → request:{repo}/{name}
    if "/" in q and not q.startswith("request:"):
        cand = "request:" + q
        if c.execute("SELECT 1 FROM nodes WHERE id=?", (cand,)).fetchone():
            return cand
    hits = [r[0] for r in c.execute("SELECT id FROM nodes WHERE id LIKE ?", (f"%{q}%",)).fetchall()]
    if len(hits) == 1:
        return hits[0]
    if len(hits) > 1:
        sys.stderr.write(f"ambiguous '{q}' -> {hits[:12]}{' ...' if len(hits) > 12 else ''}\n")
    return None

def cmd_stats(c,a):
    print("nodes:", dict(c.execute("SELECT kind,count(*) FROM nodes GROUP BY kind").fetchall()))
    print("edges:", dict(c.execute("SELECT rel,count(*) FROM edges GROUP BY rel").fetchall()))
    print("total:", c.execute("SELECT count(*) FROM nodes").fetchone()[0], "nodes,",
          c.execute("SELECT count(*) FROM edges").fetchone()[0], "edges")

def cmd_search(c,a):
    q=" ".join(a)
    try:
        rows=c.execute("SELECT n.kind,n.id,n.role,n.repo FROM node_fts f JOIN nodes n ON n.id=f.id "
                       "WHERE node_fts MATCH ? LIMIT 50", (q+"*",)).fetchall()
    except sqlite3.OperationalError:
        rows=c.execute("SELECT kind,id,role,repo FROM nodes WHERE id LIKE ? LIMIT 50",(f"%{q}%",)).fetchall()
    for r in rows: print(f"{r[0]:9} {r[1]:55} {r[2] or r[3] or ''}")
    print(f"-- {len(rows)} match(es)")

def cmd_node(c,a):
    nid=resolve(c,a[0])
    if not nid: print("not found"); return
    r=c.execute("SELECT json FROM nodes WHERE id=?", (nid,)).fetchone()
    print(r[0])
    outs=c.execute("SELECT rel,dst_id,note,src FROM edges WHERE src_id=? ORDER BY rel,seq",(nid,)).fetchall()
    ins =c.execute("SELECT rel,src_id,note,src FROM edges WHERE dst_id=? ORDER BY rel",(nid,)).fetchall()
    print(f"\nOUT ({len(outs)}):")
    for e in outs[:80]: print(f"  -{e[0]}-> {e[1]}  {e[2] or ''}  [{e[3] or '?'}]")
    print(f"\nIN ({len(ins)}):")
    for e in ins[:80]: print(f"  {e[1]} -{e[0]}->  [{e[3] or '?'}]")

def cmd_flow(c,a):
    # Record orient-session touch so orient-before-edit gate is satisfied by kg flow too.
    if a:
        _touch_orient_session(a[0])
    # bare name or repo/name — resolve() handles repo-scoped request ids
    nid=resolve(c, a[0]) or resolve(c, "request:"+a[0])
    if not nid or not str(nid).startswith("request:"):
        # try label uniquely
        nid=resolve(c, a[0])
    if not nid:
        print("request not found"); return
    rows=c.execute("SELECT seq,cond,dst_id,src,json FROM edges WHERE src_id=? AND rel='invokes' ORDER BY seq",(nid,)).fetchall()
    print(f"FLOW {nid}  ({len(rows)} processors)")
    for e in rows:
        cond="" if (e[1] or "*")=="*" else f"  [if function_code={e[1]}]"
        # prefer orch path repo over shared processor.repo (ATTR fix)
        print(f"  {e[0]:3}. {e[2].split(':',1)[1]}{cond}  [{e[3]}]")
    apis=c.execute("SELECT dst_id,src FROM edges WHERE src_id=? AND rel='calls_api'",(nid,)).fetchall()
    if apis:
        print("  external API calls:")
        for e in apis: print(f"     -> {e[0]}  [{e[1]}]")
    docs=c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='documents'",(nid,)).fetchall()
    if docs: print("  documented in:", ", ".join(d[0] for d in docs))
    dbf=dict(c.execute("SELECT rel,count(DISTINCT dst_id) FROM edges WHERE rel IN('reads','writes','deletes') "
                       "AND src_id IN (SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes') GROUP BY rel",(nid,)).fetchall())
    if dbf:
        print(f"  DB footprint: reads {dbf.get('reads',0)} / writes {dbf.get('writes',0)} / deletes {dbf.get('deletes',0)} table(s)"
              f" — `kg crud {a[0]}` for the read-set/write-set")

def cmd_deps(c,a):
    nid=resolve(c,"service:"+a[0]) or resolve(c,a[0])
    if not nid: print("service not found"); return
    print(f"{nid}\n  CALLS / DEPENDS ON:")
    for e in c.execute("SELECT rel,dst_id,note,src FROM edges WHERE src_id=? AND dst_id LIKE 'service:%'",(nid,)):
        print(f"    -{e[0]}-> {e[1].split(':',1)[1]:42} {e[2] or ''}  [{e[3]}]")
    print("  CALLED BY / TRIGGERED BY:")
    for e in c.execute("SELECT rel,src_id,note,src FROM edges WHERE dst_id=? AND src_id LIKE 'service:%'",(nid,)):
        print(f"    {e[1].split(':',1)[1]:42} -{e[0]}->  {e[2] or ''}  [{e[3]}]")

def cmd_docs(c,a):
    nid=resolve(c,a[0])
    if not nid: print("not found"); return
    rows=c.execute("SELECT rel,src_id,src FROM edges WHERE dst_id=? AND rel IN ('documents','mentions') "
                   "ORDER BY rel",(nid,)).fetchall()
    for e in rows: print(f"  {e[1]} -{e[0]}->  [{e[2]}]")
    print(f"-- {len(rows)} doc link(s) for {nid}")

def cmd_neighbors(c,a):
    rel=None; d="both"; pos=[]; i=0
    while i<len(a):
        if a[i]=="--rel": rel=a[i+1]; i+=2
        elif a[i]=="--in": d="in"; i+=1
        elif a[i]=="--out": d="out"; i+=1
        else: pos.append(a[i]); i+=1
    nid=resolve(c,pos[0])
    if not nid: print("not found"); return
    if d in ("out","both"):
        for e in c.execute("SELECT rel,dst_id,note FROM edges WHERE src_id=?"+(" AND rel=?" if rel else ""),
                           (nid,rel) if rel else (nid,)):
            print(f"OUT -{e[0]}-> {e[1]}  {e[2] or ''}")
    if d in ("in","both"):
        for e in c.execute("SELECT rel,src_id FROM edges WHERE dst_id=?"+(" AND rel=?" if rel else ""),
                           (nid,rel) if rel else (nid,)):
            print(f"IN  {e[1]} -{e[0]}->")

def cmd_impact(c,a):
    depth=3; pos=[]; i=0
    while i<len(a):
        if a[i]=="--depth": depth=int(a[i+1]); i+=2
        else: pos.append(a[i]); i+=1
    nid=resolve(c,pos[0])
    if not nid: print("not found"); return
    rows=c.execute("""
      WITH RECURSIVE up(id,d) AS (
        VALUES(?,0)
        UNION
        SELECT e.src_id, up.d+1 FROM edges e JOIN up ON e.dst_id=up.id WHERE up.d < ?
      ) SELECT DISTINCT id FROM up WHERE id<>?""",(nid,depth,nid)).fetchall()
    for r in rows[:60]: print("  ", r[0])
    print(f"-- {len(rows)} node(s) within depth {depth} would be affected by a change to {nid}")

def cmd_path(c,a):
    depth=8; pos=[]; i=0
    while i<len(a):
        if a[i]=="--depth": depth=int(a[i+1]); i+=2
        else: pos.append(a[i]); i+=1
    A=resolve(c,pos[0]); B=resolve(c,pos[1])
    if not A or not B: print("endpoint not found"); return
    row=c.execute("""
      WITH RECURSIVE p(id,path,d) AS (
        VALUES(?,?,0)
        UNION ALL
        SELECT e.dst_id, p.path||' -> '||e.dst_id, p.d+1
        FROM edges e JOIN p ON e.src_id=p.id
        WHERE p.d < ? AND instr(p.path, e.dst_id)=0
      ) SELECT path FROM p WHERE id=? ORDER BY d LIMIT 1""",(A,A,depth,B)).fetchone()
    print(row[0] if row else f"no directed path {A} -> {B} within depth {depth}")

def cmd_sql(c,a):
    q=" ".join(a)
    if not q.lower().lstrip().startswith("select"):
        sys.exit("only SELECT is allowed")
    for row in c.execute(q): print(tuple(row))

def cmd_cases(c,a):
    """Shipped fixes (from CHANGELOG). `cases` = recent; `cases <flow/table>` = precedent for that node."""
    if not a:
        for r in c.execute("SELECT id,label FROM nodes WHERE kind='case' ORDER BY id DESC LIMIT 20"):
            print(f"  {r[1]}")
        return
    nid=resolve(c,a[0])
    if not nid: print("not found"); return
    rows=c.execute("SELECT n.label,n.json FROM edges e JOIN nodes n ON n.id=e.src_id "
                   "WHERE e.dst_id=? AND e.rel='touches' AND n.kind='case'",(nid,)).fetchall()
    print(f"PRECEDENT — {len(rows)} shipped fix(es) touching {nid}:")
    import json as _j
    for r in rows:
        o=_j.loads(r[1]); tk=",".join(o.get("tickets") or []); ec=",".join(o.get("error_codes") or [])
        print(f"  [{o.get('sha','?')}] {r[0]}")
        if tk or ec: print(f"        tickets={tk or '-'}  errors={ec or '-'}  -> git show {o.get('sha','')}")

def cmd_table(c,a):
    nid=resolve(c,"table:"+a[0]) or resolve(c,a[0])
    if not nid: print("table not found"); return
    r=c.execute("SELECT json FROM nodes WHERE id=?",(nid,)).fetchone(); print(r[0])
    own=c.execute("SELECT src_id,note FROM edges WHERE dst_id=? AND rel='owns'",(nid,)).fetchall()
    print("  owned by:", ", ".join(f"{o[0].split(':',1)[1]} ({o[1]})" for o in own))
    cases=c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='touches'",(nid,)).fetchall()
    if cases: print(f"  touched by {len(cases)} case(s) — `kg cases {a[0]}`")
    docs=c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='mentions' AND src_id LIKE 'doc:%'",(nid,)).fetchall()
    for d in docs[:8]: print("  doc:", d[0])

def cmd_error(c,a):
    eid=resolve(c,"error:"+a[0]) or resolve(c,a[0])
    if not eid: print("error code not seen in any case"); return
    rows=c.execute("SELECT n.label,n.json FROM edges e JOIN nodes n ON n.id=e.src_id "
                   "WHERE e.dst_id=? AND e.rel='hit_error'",(eid,)).fetchall()
    print(f"error {eid.split(':',1)[1]} — seen in {len(rows)} case(s):")
    import json as _j
    for r in rows:
        o=_j.loads(r[1]); print(f"  [{o.get('sha','?')}] {r[0]}  -> git show {o.get('sha','')}")

def _render_diag(c, cid):
    import json as _j
    n=c.execute("SELECT json FROM nodes WHERE id=?",(cid,)).fetchone()
    if not n: return
    o=_j.loads(n["json"])
    cls=o.get("class","")
    print(f"\n● [{cls}] {o.get('label',cid)}   [{cid}]")
    for key,lbl in (("symptom","symptom  "),("src","code     "),("mechanism","mechanism"),
                    ("resolver","resolver "),("depends","depends  "),("master","config   "),
                    ("depends_table","+ data   "),("fails_to","FAILS →  "),
                    ("diagnostic","check SQL"),("fix","fix      "),
                    ("runbook","runbook  "),("reference","reference")):
        if o.get(key): print(f"    {lbl}: {o[key]}")
    pts=o.get("points")
    if pts:
        print(f"    {len(pts)} candidate silent branch(es):")
        for p in pts[:30]: print(f"        - {p}")
    # what live tables to inspect
    chk=[e["dst_id"] for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='checks'",(cid,)).fetchall()]
    if chk: print("    inspect : "+", ".join(t.split(':',1)[-1] for t in chk))

def cmd_why(c,a):
    """WHY is this value/flow wrong? — the failure-mode catalog (the 'pinpoint any issue' entrypoint).
    Reads/writes show structure; this layer shows the SILENT decision-points where bugs hide
    (wrong/zero/null/empty/missing/reverted). Two layers: curated `diag` nodes (verified root-cause +
    live SQL, claude/kg/curated/*.jsonl) and an auto per-processor silent-failure surface (every flow).
      kg why                      list the curated catalog (grouped by class)
      kg why <request>            failure surface of the whole flow: each processor's silent branches + curated diags
      kg why <processor|table>    failure modes attached to that node
      kg why <symptom-word>       e.g. zero | stuck | duplicate | missing | revert | null  -> matching diags"""
    import json as _j
    if not a:
        rows=c.execute("SELECT id,label,json FROM nodes WHERE kind='diag' AND id NOT LIKE 'diag:auto.%' ORDER BY id").fetchall()
        print(f"FAILURE-MODE catalog — {len(rows)} curated (+ auto per-processor surfaces via `kg why <request>`):")
        cur=None
        for r in rows:
            cls=_j.loads(r["json"]).get("class","?")
            if cls!=cur: print(f"\n  [{cls}]"); cur=cls
            print(f"    {r['id']}\n        {r['label']}")
        print("\n  Add a verified one: append node+edges to claude/kg/curated/diagnostics.jsonl, then build.sh")
        return
    q=a[0]
    nid=resolve(c,q)
    diags=[]
    if nid:
        row=c.execute("SELECT kind FROM nodes WHERE id=?",(nid,)).fetchone()
        if row and row["kind"]=="diag": diags.append(nid)
        # direct failure modes on this node (request/processor)
        for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='has_failure_mode'",(nid,)).fetchall():
            diags.append(e["dst_id"])
        # if it's a request, walk the whole flow: invoked processors -> their failure surfaces
        procs=[e["dst_id"] for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes'",(nid,)).fetchall()]
        for p in procs:
            for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='has_failure_mode'",(p,)).fetchall():
                diags.append(e["dst_id"])
        # if it's a table, which diags inspect it
        for e in c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='checks'",(nid,)).fetchall():
            diags.append(e["src_id"])
    if not diags:
        # symptom-word search across diag nodes (FTS)
        try:
            rows=c.execute("SELECT id FROM node_fts WHERE kind='diag' AND node_fts MATCH ? LIMIT 40",(q,)).fetchall()
        except sqlite3.OperationalError:
            rows=c.execute("SELECT id FROM nodes WHERE kind='diag' AND (id LIKE ? OR label LIKE ?)",(f"%{q}%",f"%{q}%")).fetchall()
        diags=[r["id"] for r in rows]
    seen=set(); diags=[d for d in diags if not (d in seen or seen.add(d))]
    if not diags:
        print(f"no failure-mode recorded for '{q}'.")
        print("  Try: kg why <requestName> (walks the flow's processors), or a symptom word (zero/stuck/duplicate/missing/revert).")
        print("  If this is a real new bug class, capture it: append to claude/kg/curated/diagnostics.jsonl + build.sh.")
        return
    # curated first, then auto surfaces
    cur=[d for d in diags if not d.startswith("diag:auto.")]
    auto=[d for d in diags if d.startswith("diag:auto.")]
    hdr=nid if nid else f"'{q}'"
    print(f"WHY {hdr} — {len(cur)} curated root-cause(s)"+(f" + {len(auto)} processor silent-surface(s)" if auto else "")+":")
    for d in cur: _render_diag(c,d)
    if auto:
        print(f"\n  ── auto silent-failure surface across the flow ({len(auto)} processor(s)) ──")
        for d in auto: _render_diag(c,d)

def cmd_stale(c,a):
    """Find brain docs that have drifted from code: they cite a repo file (path[:line])
    that no longer exists (renamed/moved/deleted) — a high-confidence staleness signal.
    `stale` = scan all docs; `stale <doc-substring>` = one doc."""
    import os, re
    root=ROOT
    REF=re.compile(r'\b((?:novopay-[\w.-]+|trustt-[\w.-]+)/[\w./-]+\.\w+)(?::\d+)?')
    rows=c.execute("SELECT id,src FROM nodes WHERE kind='doc'"+(" AND id LIKE ?" if a else ""),
                   (f"%{a[0]}%",) if a else ()).fetchall()
    flagged=0
    for did,src in rows:
        path=os.path.join(root, src)
        try: txt=open(path,encoding="utf-8",errors="replace").read()
        except OSError: continue
        missing=sorted({m.group(1) for m in REF.finditer(txt)
                        if "..." not in m.group(1)            # skip doc ellipsis shorthand
                        and not os.path.exists(os.path.join(root,m.group(1)))})
        if missing:
            flagged+=1
            print(f"STALE? {src}")
            for mp in missing[:6]: print(f"    cites missing: {mp}")
    print(f"-- {flagged}/{len(rows)} doc(s) cite a repo file that no longer exists (verify vs latest code)")

def _load_watermark():
    """The branch@sha the KG was built from, per repo (stamped by build.sh into stats.json)."""
    import json
    sf=os.path.join(os.path.dirname(DB),"stats.json")
    try: return json.load(open(sf)).get("watermark")
    except Exception: return None

def _git(d,*a):
    import subprocess
    try: return subprocess.check_output(["git","-C",d,*a],text=True,stderr=subprocess.DEVNULL).strip()
    except Exception: return ""

def _dirty_hash(d):
    """sha1 of (porcelain status + tracked diff), 12 chars. MUST match build.sh's formula so a
    rebuilt watermark and a live check agree. Empty string when the tree is clean."""
    import hashlib
    blob=_git(d,"status","--porcelain")+_git(d,"diff","HEAD")
    return hashlib.sha1(blob.encode("utf-8","replace")).hexdigest()[:12] if blob else ""

def _is_kg_path(path: str) -> bool:
    p = path.replace("\\", "/")
    if not p.endswith(_KG_EXTS):
        return False
    return any(h in p for h in _KG_PATH_HINTS) or p.endswith(".xml") or p.endswith(".java")

def _porcelain_paths(d):
    out = []
    for line in (_git(d, "status", "--porcelain") or "").splitlines():
        if not line.strip():
            continue
        # git porcelain: XY<space>PATH (X,Y are one char each). Be robust if a tool strips a column.
        if len(line) >= 4 and line[2] == " ":
            path = line[3:]
        elif len(line) >= 3 and line[1] == " ":
            path = line[2:]
        else:
            path = line[2:] if len(line) > 2 else line
        path = path.strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1].strip()
        if path:
            out.append(path)
    return out

def _docs_newer_than_db():
    """Cheap: is any brain doc / CHANGELOG newer than kg.db? Early-exits on first hit."""
    import glob
    try: dbm=os.path.getmtime(DB)
    except OSError: return False
    brain = os.path.join(ROOT, "cursor-bundle", "brain")
    for pat in (os.path.join(brain, "**", "*.md"),
                os.path.join(ROOT, "cursor-bundle", "brain", "changelog", "CHANGELOG.md")):
        for f in glob.iglob(pat, recursive=True):
            try:
                if os.path.getmtime(f)>dbm: return True
            except OSError: pass
    return False

_DRIFT_CACHE = None  # (mono_ts, built_at, drift, docs_stale, files)

def _drift_check():
    """Fail-closed freshness: (built_at, drift_lines, docs_stale, stale_kg_files).

    STALE when any KG-covered repo has branch/sha advance OR dirty/advanced java/xml
    under src/orchestration/deploy not reflected in the watermark dirty_hash.
    Non-kg dirty (settings.gradle, docs scripts) alone does not force STALE.
    Cached ~5s so MCP in-process queries stay ≤20ms.
    """
    import time as _time
    global _DRIFT_CACHE
    now = _time.monotonic()
    if _DRIFT_CACHE and (now - _DRIFT_CACHE[0]) < 5.0:
        return _DRIFT_CACHE[1:]
    wm=_load_watermark()
    if not wm:
        _DRIFT_CACHE = (now, None, [], False, [])
        return None, [], False, []
    root=ROOT; drift=[]; stale_files=[]
    for repo,info in wm.get("repos",{}).items():
        d=os.path.join(root,repo)
        if not os.path.isdir(os.path.join(d,".git")) and not os.path.isdir(d):
            continue
        live=_git(d,"rev-parse","--short=10","HEAD")
        if not live: continue
        wm_sha=(info.get("sha") or "")[:10]
        if live!=wm_sha:
            lb=_git(d,"rev-parse","--abbrev-ref","HEAD")
            if lb and lb!=info.get("branch"):
                drift.append(f"{repo}: KG={info.get('branch')}@{wm_sha} → now {lb}@{live}")
            else:
                drift.append(f"{repo}: KG@{wm_sha} → now @{live} (same branch, advanced)")
            full=_git(d,"rev-parse","HEAD")
            old=info.get("sha") or ""
            if old and full:
                diff=_git(d,"diff","--name-only",f"{old}..{full}")
                for p in (diff or "").splitlines():
                    if _is_kg_path(p):
                        stale_files.append(f"{repo}/{p}")
            continue
        paths=_porcelain_paths(d)
        kg_paths=[p for p in paths if _is_kg_path(p)]
        if kg_paths:
            if _dirty_hash(d)!=(info.get("dirty_hash") or ""):
                drift.append(f"{repo}: @{live} has uncommitted KG-path edits not in the KG — rebuild")
                for p in kg_paths:
                    stale_files.append(f"{repo}/{p}")
        elif info.get("dirty") and not paths:
            drift.append(f"{repo}: KG built from a dirty tree, now clean — rebuild")
    seen=set(); uniq=[]
    for f in stale_files:
        if f not in seen:
            seen.add(f); uniq.append(f)
    built = wm.get("built_at","?")
    _DRIFT_CACHE = (now, built, drift, _docs_newer_than_db(), uniq)
    return built, drift, _DRIFT_CACHE[3], uniq

def cmd_watermark(c,a):
    """Show, per repo, the branch@sha the KG knowledge was built from vs the repo's live HEAD —
    so you know exactly 'up to which branch/commit the knowledge is current'."""
    root=ROOT
    wm=_load_watermark()
    if not wm:
        print("no watermark in stats.json — rebuild with claude/kg/bin/build.sh to stamp branch@sha."); return
    import re
    RELEASE=re.compile(r'^mfi_(integration|release)_v[0-9]')
    print(f"KG built at {wm.get('built_at','?')} (UTC). Per-repo branch@sha the knowledge reflects:")
    drift=0; wip=0
    for repo,info in sorted(wm.get("repos",{}).items()):
        d=os.path.join(root,repo)
        live_b=_git(d,"rev-parse","--abbrev-ref","HEAD"); live_s=_git(d,"rev-parse","--short=10","HEAD")
        b,s=info.get("branch"),info.get("sha")
        tag=""
        if b and not RELEASE.match(b):
            base=info.get("base"); delta=info.get("feature_delta")
            if base is not None:
                tag+=f"  [WIP <- base {base} (+{delta} commits): anchor KG to {base} (upstream); base..HEAD is PROVISIONAL]"
            else:
                tag+="  [WIP-branch: base UNRESOLVED — fetch upstream; knowledge PROVISIONAL]"
            wip+=1
        if live_b and live_b!=b: tag+=f"  ⚠ BRANCH CHANGED -> now {live_b} (knowledge reflects {b})"; drift+=1
        elif live_s and live_s!=s:
            ahead=_git(d,"rev-list","--count",f"{s}..HEAD") or "?"
            tag+=f"  ⚠ {ahead} commit(s) ahead (now {live_s})"; drift+=1
        else:
            # fail-closed dirty KG paths
            kg_paths=[p for p in _porcelain_paths(d) if _is_kg_path(p)]
            if kg_paths and _dirty_hash(d)!=(info.get("dirty_hash") or ""):
                tag+=f"  ⚠ STALE KG-paths ({len(kg_paths)})"; drift+=1
        print(f"  {repo:<40} {b}@{s}{'  [dirty@build]' if info.get('dirty') else ''}{tag}")
    print(f"-- {drift} repo(s) drifted from the watermark; {wip} built off a non-release (feature/WIP) branch.")
    print("   For a WIP repo: the stable knowledge baseline is its UPSTREAM release base (shown above);")
    print("   only the base..HEAD delta is in-development. Apply the WIP-vs-stable gate (feedback_keep_knowledge_current).")

def cmd_doctor(c,a):
    import os, glob
    print("nodes/edges:", c.execute("SELECT count(*) FROM nodes").fetchone()[0],
          "/", c.execute("SELECT count(*) FROM edges").fetchone()[0])
    print("kinds:", dict(c.execute("SELECT kind,count(*) FROM nodes GROUP BY kind").fetchall()))
    dbm=os.path.getmtime(DB)
    root=ROOT
    newer=[]
    for pat in ("*/deploy/application/orchestration/**/*.xml",
                "cursor-bundle/brain/changelog/CHANGELOG.md",
                "cursor-bundle/brain/**/*.md"):
        for f in glob.glob(os.path.join(root,pat), recursive=True):
            try:
                if os.path.getmtime(f)>dbm: newer.append(os.path.relpath(f,root))
            except OSError: pass
    if newer:
        print(f"STALE: {len(newer)} source file(s) newer than kg.db — run claude/kg/bin/build.sh")
        for f in newer[:8]: print("   ", f)
    else:
        print("FRESH: kg.db is newer than all orchestration/doc/changelog sources.")
    # Branch watermark: is the KG built from the branch the repos are actually on now?
    wm=_load_watermark()
    if not wm:
        print("WATERMARK: none — rebuild to stamp per-repo branch@sha (run `kg watermark` after).")
    else:
        drift=[]
        for repo,info in wm.get("repos",{}).items():
            d=os.path.join(root,repo)
            live_b=_git(d,"rev-parse","--abbrev-ref","HEAD"); live_s=_git(d,"rev-parse","--short=10","HEAD")
            if live_b and live_b!=info.get("branch"): drift.append(f"{repo}: built {info.get('branch')} -> now {live_b}")
            elif live_s and live_s!=info.get("sha"): drift.append(f"{repo}: {info.get('sha')} -> {live_s}")
            else:
                kg_paths=[p for p in _porcelain_paths(d) if _is_kg_path(p)]
                if kg_paths and _dirty_hash(d)!=(info.get("dirty_hash") or ""):
                    drift.append(f"{repo}: {len(kg_paths)} dirty KG-path file(s)")
        if drift:
            print(f"WATERMARK DRIFT: {len(drift)} repo(s) moved since build (built {wm.get('built_at','?')}) — `kg watermark` for detail, then rebuild:")
            for x in drift[:8]: print("   ", x)
        else:
            print(f"WATERMARK: in sync — KG reflects the live branch@sha of every repo (built {wm.get('built_at','?')}).")
    # DB-access (CRUD) layer coverage
    nproc=c.execute("SELECT count(*) FROM nodes WHERE kind='processor'").fetchone()[0]
    nwith=c.execute("SELECT count(DISTINCT src_id) FROM edges WHERE rel IN('reads','writes','deletes')").fetchone()[0]
    nda=c.execute("SELECT count(*) FROM edges WHERE rel IN('reads','writes','deletes')").fetchone()[0]
    if nda:
        print(f"DB-ACCESS: {nwith}/{nproc} processors carry a CRUD edge ({nda} reads/writes/deletes) — `kg crud <flow>` / `kg writes <table>`")
    else:
        print("DB-ACCESS: no CRUD edges — run build.sh (build_dataaccess) to fold the DB-op layer in.")

def cmd_crud(c,a):
    """The full DB footprint of a flow: every processor's reads/writes/deletes, then the
    aggregate read-set / write-set / delete-set — the map a test simulator needs."""
    if not a: print("usage: kg crud <request>"); return
    nid=resolve(c,a[0]) or resolve(c,"request:"+a[0])
    if not nid: print("request not found"); return
    procs=[r[0] for r in c.execute("SELECT DISTINCT dst_id FROM edges WHERE src_id=? AND rel='invokes'",(nid,)).fetchall()]
    if not procs: print(f"{nid}: no processors"); return
    qm=",".join("?"*len(procs))
    rows=c.execute(f"SELECT src_id,rel,note,dst_id,src FROM edges WHERE rel IN('reads','writes','deletes') "
                   f"AND src_id IN ({qm}) ORDER BY src_id",procs).fetchall()
    if not rows:
        print(f"FLOW {nid}: no DB-access edges resolved (processors may be pure compute, or DAO calls unresolved)"); return
    from collections import defaultdict
    byp=defaultdict(set); reads=set(); writes=set(); deletes=set()
    for sid,rel,op,dst,src in rows:
        t=dst.split(':',1)[1]; byp[sid].add((rel,op,t))
        (reads if rel=='reads' else writes if rel=='writes' else deletes).add(t)
    print(f"DB FOOTPRINT  {nid}   ({len(byp)} of {len(procs)} processors touch the DB)")
    sym={'reads':'R','writes':'W','deletes':'D'}
    for p in sorted(byp):
        print(f"  {p.split(':',1)[1]}")
        for rel,op,t in sorted(byp[p], key=lambda x:(x[0],x[2])):
            print(f"      {sym[rel]} {t:<44} {op}")
    print(f"-- WRITE-SET  ({len(writes)}): {', '.join(sorted(writes)) or '-'}")
    print(f"-- READ-SET   ({len(reads)}): {', '.join(sorted(reads)) or '-'}")
    if deletes: print(f"-- DELETE-SET ({len(deletes)}): {', '.join(sorted(deletes))}")
    print("   write/delete-set = the state a simulation must seed & assert on (feedback_deep_rca_before_fix).")

def _reverse_db(c,a,rel,label):
    if not a: print(f"usage: kg {rel[:-1] if rel.endswith('s') else rel} <table>"); return
    nid=resolve(c,"table:"+a[0]) or resolve(c,a[0])
    if not nid: print("table not found"); return
    rows=c.execute("SELECT src_id,note,src FROM edges WHERE dst_id=? AND rel=? ORDER BY src_id",(nid,rel)).fetchall()
    print(f"{label} {nid.split(':',1)[1]} — {len(rows)} processor(s):")
    for sid,op,src in rows:
        flows=[r[0].split(':',1)[1] for r in c.execute(
            "SELECT DISTINCT src_id FROM edges WHERE dst_id=? AND rel='invokes'",(sid,)).fetchall()]
        fl=("  <- "+", ".join(flows[:4])+(" ..." if len(flows)>4 else "")) if flows else ""
        print(f"  {sid.split(':',1)[1]:<46} {op:<14}{fl}  [{src}]")

def cmd_writes(c,a):  _reverse_db(c,a,'writes','WRITERS of')
def cmd_reads(c,a):   _reverse_db(c,a,'reads','READERS of')
def cmd_deletes(c,a): _reverse_db(c,a,'deletes','DELETERS of')

def cmd_fresh(c,a):
    """Compact freshness verdict: fail-closed on dirty/advanced java/xml/orc KG paths."""
    built_at,drift,docs_stale,stale_files=_drift_check()
    if built_at is None:
        print("KG: no watermark — run claude/kg/bin/build.sh"); return
    if not drift and not docs_stale:
        print(f"KG FRESH — reflects the live checkout of every repo (built {built_at}). `kg watermark` for per-repo detail.")
        return
    if drift:
        print(f"KG STALE — built {built_at}; {len(drift)} repo(s) drifted from the live checkout:")
        for x in drift: print("   "+x)
        if stale_files:
            print(f"STALE KG-path files ({len(stale_files)}):")
            for f in stale_files: print("   "+f)
        print("(rebuild): scripts/bin/kg-switch.sh  or  cursor-bundle/kg/bin/build.sh")
    if docs_stale:
        print("NOTE: a brain doc or CHANGELOG was edited since the build — `kg search`/`docs`/`cases` text may lag; run build.sh to refold.")

def cmd_validate(c,a):
    """Integrity + min size guard — delegates to kg_validate.py (exit 1 on fail)."""
    import subprocess, sys as _s
    p=subprocess.run([_s.executable,os.path.join(HERE,"kg_validate.py")]+list(a),
                     cwd=os.path.dirname(HERE))
    if p.returncode!=0:
        raise SystemExit(p.returncode)

def cmd_orient(c,a):
    """Evidence-only map for a request: flow spine + why surface + cases. Does not invent edges."""
    if not a:
        print("Usage: kg orient <request>  — flow + why + cases (evidence only)"); return
    # Record orient timestamp for orient-before-edit gate (X4).
    _touch_orient_session(a[0] if a else "")
    print("=== ORIENT (evidence only — verify orch XML + DB before claiming) ===")
    print("--- flow ---")
    cmd_flow(c,a)
    print("--- why (silent failure surface) ---")
    cmd_why(c,a)
    print("--- cases (CHANGELOG precedents only) ---")
    cmd_cases(c,a)


def _touch_orient_session(api: str) -> None:
    """Write last orient timestamp to .cursor/kg-orient-session.json (X4 gate)."""
    import time as _time
    try:
        state_path = os.path.join(ROOT, ".cursor", "kg-orient-session.json")
        import json as _json
        existing: dict = {}
        if os.path.isfile(state_path):
            try:
                with open(state_path, encoding="utf-8") as _f:
                    existing = _json.load(_f)
            except Exception:
                pass
        existing["last_orient_ts"] = int(_time.time())
        existing["last_orient_api"] = api
        with open(state_path, "w", encoding="utf-8") as _f:
            _f.write(_json.dumps(existing) + "\n")
    except Exception:
        pass

def cmd_fixed_elsewhere(c,a):
    """Delegate cross-branch lookup; KG remains the evidence source for flow files/case SHAs."""
    if not a:
        print("Usage: kg fixed-elsewhere <apiName|processor|path|sha> [--repo R] [--base B]"); return
    import subprocess
    root=os.path.abspath(os.path.join(HERE,"../../.."))
    tool=os.path.join(root,"scripts","lib","branch_train.py")
    p=subprocess.run([sys.executable,tool,"fixed-elsewhere",*a])
    if p.returncode:
        raise SystemExit(p.returncode)

CMDS={"stats":cmd_stats,"search":cmd_search,"node":cmd_node,"flow":cmd_flow,"deps":cmd_deps,
      "docs":cmd_docs,"neighbors":cmd_neighbors,"impact":cmd_impact,"path":cmd_path,"sql":cmd_sql,
      "cases":cmd_cases,"table":cmd_table,"error":cmd_error,"why":cmd_why,"config":cmd_why,"doctor":cmd_doctor,"stale":cmd_stale,
      "watermark":cmd_watermark,"crud":cmd_crud,"writes":cmd_writes,"reads":cmd_reads,"deletes":cmd_deletes,
      "fresh":cmd_fresh,"validate":cmd_validate,"orient":cmd_orient,
      "fixed-elsewhere":cmd_fixed_elsewhere}

# Commands that READ knowledge (must be branch-correct). doctor/watermark/stats report drift
# themselves, so they're excluded to avoid a double banner.
_KNOWLEDGE_CMDS={"search","node","flow","deps","docs","neighbors","impact","path","sql",
                 "cases","table","error","why","config","crud","writes","reads","deletes",
                 "orient","fixed-elsewhere"}

def _auto_rebuild(built_at,drift):
    """On drift, rebuild the KG for the CURRENT checkout before serving the query, so analysis is
    always branch-correct. build.sh restores from the composite cache (~1s) if this branch-set was
    built before, else does a full build. Opt out with KG_NO_AUTO_REBUILD=1 (warn-only) — for
    scripts/CI that must not trigger a build. stderr keeps piped stdout clean."""
    import sys as _s, subprocess
    print(f"⟳ KG branch-drift — {len(drift)} repo(s) moved since build (built {built_at}); rebuilding "
          "for the current checkout (cache-restore if this branch-set was built before, else full build)…",file=_s.stderr)
    for x in drift[:6]: print("    "+x,file=_s.stderr)
    if len(drift)>6: print(f"    … +{len(drift)-6} more",file=_s.stderr)
    try:
        p=subprocess.run(["bash",os.path.join(HERE,"build.sh")],
                         stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,timeout=1800)
        tail=[l for l in (p.stdout or "").splitlines() if l.strip()]
        if p.returncode==0:
            note=next((l.strip() for l in tail if "restored from cache" in l or l.startswith("KG built")),
                      (tail[-1].strip() if tail else ""))
            print(f"✓ KG rebuilt — answers below are branch-correct. {note}",file=_s.stderr)
            return True
        print(f"⚠ KG rebuild failed (rc={p.returncode}) — answering from the EXISTING (stale) KG. "
              "Run claude/kg/bin/build.sh manually.",file=_s.stderr)
        if tail: print("    "+tail[-1].strip(),file=_s.stderr)
    except Exception as e:
        print(f"⚠ KG rebuild error ({e}) — answering from the EXISTING (stale) KG.",file=_s.stderr)
    return False

def main():
    argv=[a for a in sys.argv[1:] if a!="--no-drift-check"]
    nocheck=len(argv)!=len(sys.argv[1:])
    if not argv or argv[0] not in CMDS:
        print(__doc__); sys.exit(0)
    # Provenance header on knowledge answers (Upgrade 6 — one line, cheap)
    if argv[0] in _KNOWLEDGE_CMDS or argv[0] in {"fresh","watermark","validate","doctor","stats"}:
        try:
            import sys as _sys
            _lib=os.path.abspath(os.path.join(HERE,"../../../scripts/lib"))
            if _lib not in _sys.path: _sys.path.insert(0,_lib)
            from kg_state_banner import provenance_header
            print(provenance_header())
        except Exception:
            pass
    if argv[0] in _KNOWLEDGE_CMDS and not nocheck:
        import sys as _s
        built_at,drift,docs_stale,_stale_files=_drift_check()
        if drift:                                       # code/branch/dirty drift → must be branch-correct
            if os.environ.get("KG_NO_AUTO_REBUILD"):
                print(f"⚠ KG BRANCH DRIFT — knowledge may be WRONG for the current checkout "
                      f"(built {built_at}; {len(drift)} repo(s) moved). Auto-rebuild disabled "
                      "(KG_NO_AUTO_REBUILD). Rebuild: claude/kg/bin/build.sh",file=_s.stderr)
                for x in drift[:6]: print("    "+x,file=_s.stderr)
                for f in _stale_files[:12]: print("    file: "+f,file=_s.stderr)
            else:
                _auto_rebuild(built_at,drift)           # rebuilds kg.db in place; conn() below opens the fresh DB
        elif docs_stale:                                # doc-only edit → warn (docs on disk are correct; no 217s surprise)
            print("⚠ KG doc-corpus stale — a claude/ brain doc or CHANGELOG was edited since the build. "
                  "`search`/`docs`/`cases` text may lag; run claude/kg/bin/build.sh to refold (no auto-rebuild on doc edits).",file=_s.stderr)
    c=conn(); CMDS[argv[0]](c, argv[1:])

if __name__=="__main__":
    try:
        main()
    except BrokenPipeError:
        # downstream pipe (head/grep) closed early — exit quietly, no traceback
        try: sys.stdout.close()
        except Exception: pass
        os._exit(0)
