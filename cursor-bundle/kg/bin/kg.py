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
  schema <table>[.<column>]      structure + code readers/writers + train-local column flags (MCP: kg_schema)
  concept <name>                 DOMAIN SEMANTICS / FRAMEWORK bone (entity|txn_type|gl_mech|framework|…)
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
import os, sys, sqlite3, re, json
from pathlib import Path

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
        sys.exit("kg.db missing — run scripts/bin/kg-switch.sh first")
    try:
        sz = os.path.getsize(DB)
    except OSError:
        sz = 0
    if sz < 100_000:
        sys.exit(
            f"kg.db too small ({sz} bytes) — corrupt/empty; run scripts/bin/kg-switch.sh"
        )
    if readonly:
        uri = f"file:{DB}?mode=ro"
        c = sqlite3.connect(uri, uri=True)
    else:
        c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def _db_usable() -> bool:
    """True only when kg.db exists, is large enough, and has a nodes table with content."""
    if not os.path.exists(DB):
        return False
    try:
        if os.path.getsize(DB) < 100_000:
            return False
        c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        n = c.execute("SELECT count(*) FROM nodes").fetchone()[0]
        c.close()
        return n >= 3000
    except Exception:
        return False

def resolve(c, q):
    """Resolve a node id. Requests are repo-scoped (request:{repo}/{name}); bare
    names resolve by unique label. Use repo/name when ambiguous.

    Prefer unique request *label* before scheduler:/topic: prefixes — many EOD
    jobs share the Request name as a scheduler id (e.g. interestAccrualCalculation)
    and the bare prefix loop would otherwise return an empty scheduler spine.
    """
    if c.execute("SELECT 1 FROM nodes WHERE id=?", (q,)).fetchone():
        return q
    # Unique request label BEFORE scheduler:/topic: (same bare name collision).
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
    for pref in ("request:", "service:", "processor:", "api:", "doc:", "topic:", "scheduler:", "table:", "symbol:"):
        if c.execute("SELECT 1 FROM nodes WHERE id=?", (pref + q,)).fetchone():
            return pref + q
    # Unique Java method: Class#method or bare method name → symbol:*
    if q.startswith("symbol:"):
        return None
    sym_hits = [r[0] for r in c.execute(
        "SELECT id FROM nodes WHERE kind='symbol' AND (label=? OR label LIKE ? OR id LIKE ?)",
        (q, f"%#{q}", f"%#{q}"),
    ).fetchall()]
    if len(sym_hits) == 1:
        return sym_hits[0]
    if len(sym_hits) > 1:
        if "#" in q:
            exact = [r for r in sym_hits if r.endswith("/" + q) or r.endswith(":" + q)]
            if len(exact) == 1:
                return exact[0]
        sys.stderr.write(f"ambiguous symbol '{q}' -> {sym_hits[:8]}{' ...' if len(sym_hits) > 8 else ''}\n")
        sys.stderr.write("  hint: use Class#method e.g. InterestAccrualBookingService#adjustChildLoanAccountsInterestAccrual\n")
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

_SEMANTICS_KINDS = (
    "entity", "txn_type", "gl_mech", "gl_rule", "batch_cfg", "redis_key", "framework", "server", "activation",
)

def cmd_search(c,a):
    q=" ".join(a)
    # Error-code fold (MCP kg_error removed): numeric / ACCT_* → deepen via cmd_error first.
    bare = q.strip()
    if bare and (bare.isdigit() or bare.upper().startswith("ACCT") or bare.upper().startswith("NOV-")):
        cmd_error(c, [bare])
        print("--")
    try:
        rows=c.execute("SELECT n.kind,n.id,n.role,n.repo FROM node_fts f JOIN nodes n ON n.id=f.id "
                       "WHERE node_fts MATCH ? LIMIT 50", (q+"*",)).fetchall()
    except sqlite3.OperationalError:
        rows=c.execute("SELECT kind,id,role,repo FROM nodes WHERE id LIKE ? LIMIT 50",(f"%{q}%",)).fetchall()
    # Prefer semantics/framework kinds when present (surface bone answers first)
    pref = [r for r in rows if r[0] in _SEMANTICS_KINDS]
    rest = [r for r in rows if r[0] not in _SEMANTICS_KINDS]
    ordered = pref + rest
    for r in ordered: print(f"{r[0]:9} {r[1]:55} {r[2] or r[3] or ''}")
    print(f"-- {len(ordered)} match(es)")

def cmd_concept(c,a):
    """Domain semantics + framework bone lookup (LEAN — no new MCP tool required).

    Usage: kg concept <name>   e.g. LOAN_PREPAYMENT | loan_due_details | autoflush | Redis TTL
    """
    if not a:
        print("usage: kg concept <entity|txn_type|framework keyword>")
        print("kinds:", ", ".join(_SEMANTICS_KINDS))
        return
    q = " ".join(a).strip()
    aliases = {
        "transaction boundary": "spring.txn",
        "txn boundary": "spring.txn",
        "orchestrator txn": "spring.txn",
        "server.port": "server:",
        "tomcat": "server:",
        "chunk": "batch_cfg",
        "skip retry": "batch_cfg",
        "iad": "interest_accrual_details",
        "loan_account_dues": "loan_due_details",  # no such table — redirect with note
    }
    ql = q.lower()
    redirect_note = None
    if ql in aliases:
        if ql == "loan_account_dues":
            redirect_note = (
                "NOTE: no @Entity/@Table loan_account_dues in money repos — "
                "closest typed entity is loan_due_details (per-component dues)."
            )
        q = aliases[ql]
    # Exact id / label first across semantics kinds
    rows = c.execute(
        "SELECT kind,id,label,json FROM nodes WHERE kind IN ({}) AND "
        "(id=? OR id=? OR id=? OR id=? OR id=? OR id=? OR label=? OR id LIKE ? OR label LIKE ?) "
        "LIMIT 40".format(",".join("?" * len(_SEMANTICS_KINDS))),
        (*_SEMANTICS_KINDS,
         f"entity:{q}", f"txn_type:{q}", f"framework:{q}", f"gl_mech:{q}", f"redis_key:{q}",
         f"batch_cfg:{q}",
         q, f"%{q}%", f"%{q}%"),
    ).fetchall()
    if not rows:
        # FTS fallback restricted to semantics kinds
        try:
            rows = c.execute(
                "SELECT n.kind,n.id,n.label,n.json FROM node_fts f JOIN nodes n ON n.id=f.id "
                "WHERE n.kind IN ({}) AND node_fts MATCH ? LIMIT 30".format(
                    ",".join("?" * len(_SEMANTICS_KINDS))
                ),
                (*_SEMANTICS_KINDS, q.replace(":", " ") + "*"),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
    if not rows and q.startswith("server:"):
        rows = c.execute(
            "SELECT kind,id,label,json FROM nodes WHERE kind='server' LIMIT 20"
        ).fetchall()
    if not rows and q == "batch_cfg":
        rows = c.execute(
            "SELECT kind,id,label,json FROM nodes WHERE kind='batch_cfg' AND json LIKE '%chunk%' LIMIT 15"
        ).fetchall()
    if not rows:
        print("not found — try kg search, or check UNKNOWN semantics index (kg node semantics:unknown_index)")
        return
    # Prefer exact label / exact entity:id / framework containing query
    def _rank(row):
        kind, nid, label, _js = row
        if label == q or nid.endswith(":" + q) or nid == q:
            return 0
        if nid == f"entity:{q}" or nid == f"txn_type:{q}":
            return 0
        if q in nid or q in (label or ""):
            return 1
        return 2
    rows = sorted(rows, key=_rank)
    if redirect_note:
        print(redirect_note)
    for kind, nid, label, js in rows[:12]:
        try:
            o = json.loads(js)
        except Exception:
            o = {}
        print(f"=== {kind}  {nid}  ({label}) ===")
        if o.get("purpose"):
            print(f"purpose: {o['purpose']}")
        if o.get("note"):
            print(f"note: {o['note']}")
        if o.get("unknown"):
            print(f"UNKNOWN: {o['unknown']}")
        if o.get("key_columns"):
            print(f"key_columns: {', '.join(o['key_columns'][:16])}")
        if o.get("creators"):
            for cr in o["creators"][:5]:
                print(f"  creator: {cr.get('src')}")
        if o.get("chunk") is not None:
            print(f"chunk: {o['chunk']}")
        if o.get("port") is not None:
            print(f"port: {o['port']}")
        if o.get("ttl"):
            print(f"ttl: {o['ttl']}  {o.get('ttl_notes') or ''}")
        print(f"src: {o.get('src') or '?'}")
        outs = c.execute(
            "SELECT rel,dst_id,note FROM edges WHERE src_id=? ORDER BY rel LIMIT 12", (nid,)
        ).fetchall()
        for e in outs:
            print(f"  -{e[0]}-> {e[1]}  {e[2] or ''}")
        print()


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

def _pop_require_align(a):
    """Pull --require-repo/--require-branch (or env KG_ALIGN_*) and fail-closed if misaligned.

    Returns remaining argv. Used by money look-ups so branch-wrong KG cannot silently answer.
    Nested calls under orient set _pop_require_align._nested to avoid double-fail/hint.
    """
    repo=None; branch=None; rest=[]; i=0
    while i<len(a):
        if a[i]=="--require-repo" and i+1<len(a): repo=a[i+1]; i+=2
        elif a[i]=="--require-branch" and i+1<len(a): branch=a[i+1]; i+=2
        else: rest.append(a[i]); i+=1
    if getattr(_pop_require_align, "_nested", False):
        return rest
    repo=repo or os.environ.get("KG_ALIGN_REPO") or ""
    branch=branch or os.environ.get("KG_ALIGN_BRANCH") or ""
    if repo and branch:
        cmd_align(None, ["--repo", repo, "--branch", branch])
    elif os.environ.get("KG_REQUIRE_ALIGN") in ("1", "true", "yes"):
        print("ALIGN REQUIRED — pass --require-repo/--require-branch or set KG_ALIGN_REPO+KG_ALIGN_BRANCH "
              "(or call `kg align` / MCP kg_align first).", file=sys.stderr)
        raise SystemExit(2)
    else:
        if not getattr(_pop_require_align, "_hinted", False):
            wm=_load_watermark() or {}
            acc=(wm.get("repos") or {}).get("trustt-platform-accounting") or {}
            if acc.get("branch"):
                print(f"ALIGN HINT: KG accounting={acc.get('branch')} — for train-correct impact use "
                      f"`kg align --repo trustt-platform-accounting --branch <train>` or "
                      f"--require-repo/--require-branch", file=sys.stderr)
            _pop_require_align._hinted = True  # type: ignore[attr-defined]
    return rest


def cmd_flow(c,a):
    # Display-only noise filter. `dummyProcessor` is a real orchestration entry (a control
    # anchor), so it is never dropped from the index — only from the default view, and the
    # hidden count is always reported. `--raw` restores it.
    raw_view = "--raw" in a
    a = [x for x in a if x != "--raw"]
    a=_pop_require_align(a)
    # Record orient-session touch so orient-before-edit gate is satisfied by kg flow too.
    if a:
        _touch_orient_session(a[0])
    # bare name or repo/name — resolve() prefers unique request label over scheduler:
    nid=resolve(c, a[0]) or resolve(c, "request:"+a[0])
    if nid and str(nid).startswith("scheduler:"):
        bare = nid.split(":", 1)[1]
        rhits = [r[0] for r in c.execute(
            "SELECT id FROM nodes WHERE kind='request' AND label=?", (bare,)
        ).fetchall()]
        if len(rhits) == 1:
            nid = rhits[0]
    if not nid or not str(nid).startswith("request:"):
        nid=resolve(c, a[0])
    if not nid:
        print("request not found"); return
    if not str(nid).startswith("request:"):
        print(f"not a request flow: {nid} (use request:<repo>/<name> or bare Request label)"); return
    rows=c.execute("SELECT seq,cond,dst_id,src,json FROM edges WHERE src_id=? AND rel='invokes' ORDER BY seq",(nid,)).fetchall()
    nested=c.execute("SELECT dst_id,note,src FROM edges WHERE src_id=? AND rel='calls'",(nid,)).fetchall()
    total_rows = len(rows)
    hidden = 0
    if not raw_view:
        keep = [r for r in rows if r[2].split(":", 1)[-1] != "dummyProcessor"]
        hidden = len(rows) - len(keep)
        rows = keep
    thrown = {
        r[0]: r[1]
        for r in c.execute(
            "SELECT src_id,count(DISTINCT dst_id) FROM edges WHERE rel='throws' "
            "AND src_id IN (SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes') "
            "GROUP BY src_id", (nid,)
        ).fetchall()
    }
    print(f"FLOW {nid}  ({total_rows} processors)")
    if hidden:
        print(f"  [view] {hidden} dummyProcessor control anchor(s) hidden — `--raw` to show all")
    _cap = getattr(cmd_flow, "_brief_cap", None)
    if _cap and len(rows) > _cap:
        head, tail_n = rows[:_cap], len(rows) - _cap
        print(f"  [brief] showing first {_cap} of {len(rows)} — `kg flow {nid.split('/')[-1]}` for the full chain")
        rows = head
    else:
        tail_n = 0
    for e in rows:
        cond="" if (e[1] or "*")=="*" else f"  [if function_code={e[1]}]"
        n_thr = thrown.get(e[2], 0)
        mark = f"  ⚠throws:{n_thr}" if n_thr else ""
        # prefer orch path repo over shared processor.repo (ATTR fix)
        print(f"  {e[0]:3}. {e[2].split(':',1)[1]}{cond}{mark}  [{e[3]}]")
    if nested:
        print(f"  nested internal Request(s) ({len(nested)}):")
        for e in nested:
            note = f" — {e[1]}" if e[1] else ""
            print(f"     -> {e[0]}{note}  [{e[2]}]")
    apis=c.execute("SELECT dst_id,src FROM edges WHERE src_id=? AND rel='calls_api'",(nid,)).fetchall()
    if apis:
        print("  external API calls:")
        for e in apis: print(f"     -> {e[0]}  [{e[1]}]")
    docs=c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='documents'",(nid,)).fetchall()
    if tail_n:
        print(f"  … +{tail_n} more processor(s) elided in brief mode")
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
    a=_pop_require_align(a)
    depth=3; pos=[]; i=0
    while i<len(a):
        if a[i]=="--depth": depth=int(a[i+1]); i+=2
        else: pos.append(a[i]); i+=1
    if not pos:
        print("Usage: kg impact <node|Class#method|method> [--depth N] [--require-repo R --require-branch B]"); return
    nid=resolve(c,pos[0])
    if not nid:
        # Retry as method-only symbol search (impact analysis entry)
        hits=[r[0] for r in c.execute(
            "SELECT id FROM nodes WHERE kind='symbol' AND (label LIKE ? OR id LIKE ?) LIMIT 12",
            (f"%#{pos[0]}", f"%#{pos[0]}"),
        ).fetchall()]
        if len(hits)==1:
            nid=hits[0]
        elif hits:
            print(f"ambiguous method '{pos[0]}' — pick one:")
            for h in hits: print(" ", h)
            return
        else:
            print("not found"); return
    # Always show which accounting train this KG reflects (branch-wise impact hygiene)
    wm=_load_watermark() or {}
    acc=(wm.get("repos") or {}).get("trustt-platform-accounting") or {}
    if acc:
        print(f"IMPACT KG train: accounting={acc.get('branch','?')}@{acc.get('sha','?')} "
              f"(built {wm.get('built_at','?')}) — misaligned? kg align --repo trustt-platform-accounting --branch <train>")
    # Framework-aware warning when touching platform-lib paths / framework nodes
    q0 = pos[0]
    if ("platform-lib" in q0 or "infra-" in q0 or str(nid).startswith("framework:")
            or str(nid).startswith("activation:framework")):
        print("FRAMEWORK WARNING: change under platform-lib / framework:* has cross-service blast radius "
              "(all services scanning in.novopay). See kg concept platform_lib / framework:platform_lib.blast_radius.")
        blast = c.execute(
            "SELECT id,label FROM nodes WHERE id='framework:platform_lib.blast_radius' OR id LIKE 'framework:%' LIMIT 8"
        ).fetchall()
        for b in blast:
            print(f"  framework-hint: {b[0]}  {b[1]}")
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

def _error_template(code):
    """Resolve the message template for a code.

    Numeric error templates exist ONLY at runtime (Redis db2 / notification_message);
    no repo carries them. So this is never branch truth — the provenance label says so
    and the caller must not present it as train-verified.
    """
    import subprocess
    for db, key in ((2, f"localmfi_{code}_en-in"), (2, f"localmfi_{code}")):
        try:
            out = subprocess.run(
                ["redis-cli", "-n", str(db), "get", key],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
        except Exception:
            return None, None
        if out and out not in ("", "(nil)"):
            return out.strip('"'), f"redis db{db}:{key} (RUNTIME, not branch truth)"
    return None, None


def cmd_error(c,a):
    """Deep error lookup: source-derived throw sites + required EC keys + cases."""
    if not a:
        print("usage: kg error <code> [--no-template]"); return
    a = _pop_require_align(a)
    args = [x for x in a if not str(x).startswith("--")]
    want_tpl = "--no-template" not in a
    if not args:
        print("usage: kg error <code> [--no-template]"); return
    code = str(args[0]).strip()
    eid = resolve(c, "error:" + code) or resolve(c, code)
    import json as _j

    throws = c.execute(
        "SELECT src,json FROM edges WHERE dst_id=? AND rel='throws' ORDER BY src",
        (f"error:{code}",),
    ).fetchall()
    if throws:
        print(f"error {code} — {len(throws)} throw site(s) [source-derived]")
        keys, branches = [], []
        for src, ej in throws:
            o = _j.loads(ej) if ej else {}
            frm = (o.get("from") or "").split(":", 1)[-1]
            sev = o.get("severity", "?")
            via = o.get("resolved_via", "")
            br = o.get("branch") or "?"
            if br not in branches:
                branches.append(br)
            print(f"  {sev:9} {frm}")
            print(f"            {src}  [{br}]" + (f"  via {via}" if via != "literal" else ""))
            for k in (o.get("ctx_keys") or "").split(","):
                if k and k not in keys:
                    keys.append(k)
        if keys:
            print(f"  requires EC keys: {', '.join(keys)}")
            print("    (the ${...} placeholders the message template substitutes; a blank")
            print("     message means these were not in the ExecutionContext at resolve time)")
        if len(branches) > 1:
            print(f"  ⚠ thrown on multiple branches: {', '.join(branches)} — verify per train")
        if want_tpl:
            tpl, prov = _error_template(code)
            if tpl:
                print(f"  template: {tpl}")
                print(f"    source: {prov}")

    if eid:
        nrow = c.execute("SELECT id,label,json FROM nodes WHERE id=?", (eid,)).fetchone()
        src = ""
        if nrow and nrow[2]:
            try:
                src = (_j.loads(nrow[2]) or {}).get("src") or ""
            except Exception:
                src = ""
        if not throws:
            print(f"error {eid.split(':',1)[1]}  src={src or '?'}")
        rows = c.execute(
            "SELECT n.label,n.json FROM edges e JOIN nodes n ON n.id=e.src_id "
            "WHERE e.dst_id=? AND e.rel='hit_error'",
            (eid,),
        ).fetchall()
        if rows or not throws:
            print(f"  hit_error cases: {len(rows)}")
        for r in rows:
            o = _j.loads(r[1]) if r[1] else {}
            # Workspace/harness changelog entries carry no commit sha — printing
            # `[None] … -> git show None` offers a command that cannot work.
            sha = o.get("sha") or ""
            print(f"  [{sha or 'no-sha'}] {r[0]}" + (f"  -> git show {sha}" if sha else ""))
            for k in ("files", "paths", "touched"):
                if o.get(k):
                    print(f"    {k}: {o.get(k)}")
                    break
    elif not throws:
        print(f"error code {code!r} — no error: node")
    # FTS / label scan for throw sites & diags mentioning the code
    hits = []
    try:
        hits = c.execute(
            "SELECT id,kind,label FROM nodes WHERE label LIKE ? OR id LIKE ? LIMIT 12",
            (f"%{code}%", f"%{code}%"),
        ).fetchall()
    except Exception:
        hits = []
    if hits and not throws:
        print(f"  related nodes ({len(hits)}):")
        for nid, kind, lab in hits:
            print(f"    [{kind}] {nid}  {lab}")
    if not throws and not eid:
        # NOT_INDEXED is a coverage statement, never "this code does not exist".
        print(f"NOT_INDEXED: {code} has no throw site in the current KG build.")
        print("  Absence here is NOT proof the code is unused — it means one of:")
        print("    * thrown dynamically (`new NovopayFatalException(errorCode)`) — never indexed")
        print("    * thrown on a branch this build did not read (`kg watermark`)")
        print("    * raised by config/DB rather than Java")
        print(f"  Verify before concluding:  grep -rn '\"{code}\"' --include=*.java .")
def _request_aliases(c, nid):
    """All request node ids sharing the same label (handles repo-scoped vs legacy ids)."""
    if not nid or not str(nid).startswith("request:"):
        return [nid] if nid else []
    row = c.execute("SELECT label FROM nodes WHERE id=?", (nid,)).fetchone()
    if not row or not row["label"]:
        return [nid]
    hits = [r[0] for r in c.execute(
        "SELECT id FROM nodes WHERE kind='request' AND label=?", (row["label"],)
    ).fetchall()]
    return hits or [nid]


def _resolve_api_to_requests(c, api_nid):
    """Map api:{name} to request node(s) with the same label."""
    row = c.execute("SELECT label FROM nodes WHERE id=?", (api_nid,)).fetchone()
    if not row or not row["label"]:
        return []
    return [r[0] for r in c.execute(
        "SELECT id FROM nodes WHERE kind='request' AND label=?", (row["label"],)
    ).fetchall()]


def _failure_modes_on(c, node_id):
    return [e["dst_id"] for e in c.execute(
        "SELECT dst_id FROM edges WHERE src_id=? AND rel='has_failure_mode'", (node_id,)
    ).fetchall()]


def _expand_related_diags(c, diags, hops=1):
    """Follow curated diag `related` edges (bounded) so parent orient surfaces linked RCAs."""
    curated = [d for d in diags if d.startswith("diag:") and not d.startswith("diag:auto.")]
    for _ in range(max(0, hops)):
        extra = []
        for d in list(curated):
            for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='related'", (d,)).fetchall():
                dst = e["dst_id"]
                if dst.startswith("diag:") and not dst.startswith("diag:auto."):
                    extra.append(dst)
        for d in extra:
            if d not in curated:
                curated.append(d)
        diags.extend(extra)
    return diags


def _collect_flow_failure_diags(c, start_nid, *, related_hops=1):
    """Transitive failure surface for a request: orch processors + nested internal calls + symbols."""
    seeds = _request_aliases(c, start_nid)
    visit_req = set(seeds)
    visit_proc = set()
    curated = []
    auto = []

    def _absorb(node_id):
        for d in _failure_modes_on(c, node_id):
            if d.startswith("diag:auto."):
                auto.append(d)
            elif d.startswith("diag:"):
                curated.append(d)

    queue = list(seeds)
    while queue:
        req = queue.pop(0)
        _absorb(req)
        for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes'", (req,)).fetchall():
            proc = e["dst_id"]
            if proc in visit_proc:
                continue
            visit_proc.add(proc)
            _absorb(proc)
            for sym in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='implements'", (proc,)).fetchall():
                _absorb(sym["dst_id"])
            for e2 in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='calls'", (proc,)).fetchall():
                dst = e2["dst_id"]
                if dst.startswith("request:") and dst not in visit_req:
                    visit_req.add(dst)
                    queue.append(dst)
        for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='calls_api'", (req,)).fetchall():
            for rq in _resolve_api_to_requests(c, e["dst_id"]):
                if rq not in visit_req:
                    visit_req.add(rq)
                    queue.append(rq)
        for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='calls'", (req,)).fetchall():
            dst = e["dst_id"]
            if dst.startswith("request:") and dst not in visit_req:
                visit_req.add(dst)
                queue.append(dst)
    all_diags = curated + auto
    all_diags = _expand_related_diags(c, all_diags, related_hops)
    seen = set()
    curated = [d for d in all_diags if d.startswith("diag:") and not d.startswith("diag:auto.")
               and not (d in seen or seen.add(d))]
    seen_auto = set()
    auto = [d for d in all_diags if d.startswith("diag:auto.") and not (d in seen_auto or seen_auto.add(d))]
    return curated, auto, visit_proc, visit_req


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

def _pop_auto_cap(a):
    """Optional --auto-cap N limits auto silent-surface diags (MCP/orient use)."""
    cap = None
    rest = []
    i = 0
    while i < len(a):
        if a[i] == "--auto-cap" and i + 1 < len(a):
            cap = int(a[i + 1])
            i += 2
        else:
            rest.append(a[i])
            i += 1
    if cap is not None:
        cmd_why._auto_cap = cap  # type: ignore[attr-defined]
    return rest


def cmd_why(c,a):
    """WHY is this value/flow wrong? — the failure-mode catalog (the 'pinpoint any issue' entrypoint).
    Reads/writes show structure; this layer shows the SILENT decision-points where bugs hide
    (wrong/zero/null/empty/missing/reverted). Two layers: curated `diag` nodes (verified root-cause +
    live SQL, claude/kg/curated/*.jsonl) and an auto per-processor silent-failure surface (every flow).
      kg why                      list the curated catalog (grouped by class)
      kg why <request>            failure surface of the whole flow: each processor's silent branches + curated diags
      kg why <processor|table>    failure modes attached to that node
      kg why <symptom-word>       e.g. zero | stuck | duplicate | missing | revert | null  -> matching diags"""
    a=_pop_require_align(a)
    prev_cap = getattr(cmd_why, "_auto_cap", None)
    a = _pop_auto_cap(a)
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
        cmd_why._auto_cap = prev_cap  # type: ignore[attr-defined]
        return
    try:
        q=a[0]
        nid=resolve(c,q)
        diags=[]
        if nid:
            row=c.execute("SELECT kind FROM nodes WHERE id=?",(nid,)).fetchone()
            if row and row["kind"]=="diag": diags.append(nid)
            if row and row["kind"]=="request":
                cur, auto, _, nested = _collect_flow_failure_diags(c, nid)
                diags.extend(cur)
                diags.extend(auto)
                if len(nested) > len(_request_aliases(c, nid)):
                    nested_only = sorted(nested - set(_request_aliases(c, nid)))
                    print(f"  (nested internal flow(s): {', '.join(r.split(':',1)[-1] for r in nested_only)})",
                          file=sys.stderr)
            elif row and row["kind"]=="processor":
                diags.extend(_failure_modes_on(c, nid))
                for sym in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='implements'", (nid,)).fetchall():
                    diags.extend(_failure_modes_on(c, sym["dst_id"]))
            elif row and row["kind"]=="symbol":
                diags.extend(_failure_modes_on(c, nid))
            else:
                diags.extend(_failure_modes_on(c, nid))
                procs=[e["dst_id"] for e in c.execute("SELECT dst_id FROM edges WHERE src_id=? AND rel='invokes'",(nid,)).fetchall()]
                for p in procs:
                    diags.extend(_failure_modes_on(c, p))
            for e in c.execute("SELECT src_id FROM edges WHERE dst_id=? AND rel='checks'",(nid,)).fetchall():
                diags.append(e["src_id"])
        if not diags:
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
        cur=[d for d in diags if not d.startswith("diag:auto.")]
        auto=[d for d in diags if d.startswith("diag:auto.")]
        auto_cap = getattr(cmd_why, "_auto_cap", None)
        if auto_cap is not None:
            auto = auto[: max(0, int(auto_cap))]
        hdr=nid if nid else f"'{q}'"
        print(f"WHY {hdr} — {len(cur)} curated root-cause(s)"+(f" + {len(auto)} processor silent-surface(s)" if auto else "")+":")
        for d in cur: _render_diag(c,d)
        if auto:
            total_auto = len([d for d in diags if d.startswith("diag:auto.")])
            omitted = total_auto - len(auto)
            print(f"\n  ── auto silent-failure surface across the flow ({len(auto)} processor(s)"
                  + (f"; {omitted} more omitted — use CLI `kg why` for full list)" if omitted else "")
                  + ") ──")
            for d in auto: _render_diag(c,d)
    finally:
        cmd_why._auto_cap = prev_cap  # type: ignore[attr-defined]

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
    try:
        with open(sf, encoding="utf-8") as f:
            return json.load(f).get("watermark")
    except Exception:
        return None

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
    # Serial on purpose. This runs inside the MCP server's provenance header, under a per-tool
    # wall-clock cap enforced by a daemon thread. A ThreadPoolExecutor here re-creates the
    # 2026-07-30 hang: `with` calls shutdown(wait=True), which blocks on a worker the server has
    # already abandoned, and its non-daemon threads then block process exit. See _run_timed in
    # cursor-bundle/kg/mcp/kg_mcp_server.py.
    _pre={}
    for _r in wm.get("repos",{}):
        _d=os.path.join(root,_r)
        if not os.path.isdir(os.path.join(_d,".git")) and not os.path.isdir(_d):
            continue
        _pre[_r]=(_git(_d,"rev-parse","--short=10","HEAD"),_porcelain_paths(_d))
    for repo,info in wm.get("repos",{}).items():
        d=os.path.join(root,repo)
        if repo not in _pre:
            continue
        live,_paths=_pre[repo]
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
        paths=_paths
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
    if not _db_usable():
        print(
            "KG INVALID — kg.db missing/empty/corrupt (refusing watermark). "
            "Run: scripts/bin/kg-switch.sh"
        )
        raise SystemExit(1)
    root=ROOT
    wm=_load_watermark()
    if not wm:
        print("no watermark in stats.json — rebuild with scripts/bin/kg-switch.sh to stamp branch@sha."); return
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
    """Health: validate + fresh + node/edge + source/watermark staleness (MCP kg_fresh/kg_validate folded here)."""
    import os, glob
    # --- former MCP kg_validate / kg_fresh ---
    try:
        cmd_validate(c, [])
    except SystemExit as exc:
        print(f"VALIDATE_EXIT: {exc.code}")
    try:
        cmd_fresh(c, [])
    except SystemExit as exc:
        print(f"FRESH_EXIT: {exc.code}")
    print("---")
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
    # Semantics + framework bone coverage (staleness signal if kinds missing after rebuild)
    sk = dict(c.execute(
        "SELECT kind,count(*) FROM nodes WHERE kind IN ('entity','txn_type','gl_mech','gl_rule','batch_cfg',"
        "'redis_key','framework','server','activation') GROUP BY kind"
    ).fetchall())
    if sk:
        print(f"SEMANTICS-BONE: {sk} — `kg concept <name>` / search prefers these kinds")
    else:
        print("SEMANTICS-BONE: MISSING — run build.sh (build_semantics_bone + build_activation); doctor expects these kinds after rebuild.")
    # Rebuild staleness: builder script newer than kg.db
    for bone_name in ("build_semantics_bone.py", "build_semantics_closeup.py"):
        bone = os.path.join(HERE, bone_name)
        try:
            if os.path.isfile(bone) and os.path.getmtime(bone) > dbm:
                print(f"STALE-BONE: {bone_name} newer than kg.db — force rebuild to refresh semantics/framework nodes.")
        except OSError:
            pass

def cmd_crud(c,a):
    """The full DB footprint of a flow: every processor's reads/writes/deletes, then the
    aggregate read-set / write-set / delete-set — the map a test simulator needs."""
    a=_pop_require_align(a)
    if not a: print("usage: kg crud <request> [--require-repo R --require-branch B]"); return
    nid=resolve(c,a[0]) or resolve(c,"request:"+a[0])
    if nid and str(nid).startswith("scheduler:"):
        bare = nid.split(":", 1)[1]
        rhits = [r[0] for r in c.execute(
            "SELECT id FROM nodes WHERE kind='request' AND label=?", (bare,)
        ).fetchall()]
        if len(rhits) == 1:
            nid = rhits[0]
    if not nid: print("request not found"); return
    if not str(nid).startswith("request:"):
        print(f"not a request flow: {nid}"); return
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

def cmd_writes(c,a):
    a=_pop_require_align(a)
    _reverse_db(c,a,'writes','WRITERS of')
def cmd_reads(c,a):   _reverse_db(c,a,'reads','READERS of')
def cmd_deletes(c,a): _reverse_db(c,a,'deletes','DELETERS of')

def cmd_fresh(c,a):
    """Compact freshness verdict: fail-closed on dirty/advanced java/xml/orc KG paths."""
    if not _db_usable():
        print(
            "KG INVALID — kg.db missing/empty/corrupt (refusing FRESH). "
            "Run: scripts/bin/kg-switch.sh"
        )
        raise SystemExit(1)
    built_at,drift,docs_stale,stale_files=_drift_check()
    # Always surface WIP provisional repos on money-safe answers
    wm=_load_watermark() or {}
    wip=[]
    for repo,meta in (wm.get("repos") or {}).items():
        br=(meta or {}).get("branch") or ""
        if br.startswith("feature/") or (meta or {}).get("wip") or "WIP" in str((meta or {}).get("note") or ""):
            wip.append(f"{repo.split('trustt-platform-')[-1].split('novopay-platform-')[-1]}={br[:24]}")
    # Also detect from watermark tags written at build
    if not wip:
        for repo,meta in (wm.get("repos") or {}).items():
            br=(meta or {}).get("branch") or ""
            if br and not re.match(r"^mfi_(integration|release)_v", br):
                short=repo.replace("trustt-platform-","").replace("novopay-platform-","")
                wip.append(f"{short}={br[:24]}")
    prov = f" PROVISIONAL:{','.join(wip)}" if wip else ""
    if built_at is None:
        print("KG: no watermark — run scripts/bin/kg-switch.sh"); return
    if not drift and not docs_stale:
        print(f"KG FRESH — reflects the live checkout of every repo (built {built_at}). `kg watermark` for per-repo detail.{prov}")
        return
    if drift:
        print(f"KG STALE — built {built_at}; {len(drift)} repo(s) drifted from the live checkout:{prov}")
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
    # Capture stdout — MCP stdio must stay JSON-RPC-only (never inherit fd1).
    p=subprocess.run([_s.executable,os.path.join(HERE,"kg_validate.py")]+list(a),
                     cwd=os.path.dirname(HERE),
                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.stdout:
        print(p.stdout, end="" if p.stdout.endswith("\n") else "\n")
    if p.returncode!=0:
        raise SystemExit(p.returncode)

def cmd_align(c,a):
    """Fail-closed: KG watermark must match expected repo@branch for impact analysis.

    Usage:
      kg align --repo trustt-platform-accounting --branch mfi_integration_v3.4.2.4
      kg align --domain accounting --train mfi_integration_v3.4.2.4
    Exit 0 = aligned; exit 2 = mismatch (do not trust impact/flow for that train).
    """
    repo=None; branch=None; domain=None; train=None; i=0
    while i<len(a):
        if a[i]=="--repo" and i+1<len(a): repo=a[i+1]; i+=2
        elif a[i]=="--branch" and i+1<len(a): branch=a[i+1]; i+=2
        elif a[i]=="--domain" and i+1<len(a): domain=a[i+1]; i+=2
        elif a[i]=="--train" and i+1<len(a): train=a[i+1]; i+=2
        else: i+=1
    expectations=[]
    if repo and branch:
        expectations.append((repo, branch))
    if domain and train:
        try:
            import sys as _s
            _lib=os.path.abspath(os.path.join(HERE,"../../../scripts/lib"))
            if _lib not in _s.path: _s.path.insert(0,_lib)
            from train_banner import DOMAIN_REPOS
            for r in DOMAIN_REPOS.get(domain) or []:
                expectations.append((r, train))
        except Exception as e:
            print(f"align: cannot load DOMAIN_REPOS ({e})")
            raise SystemExit(2)
    if not expectations:
        print("Usage: kg align --repo <repo> --branch <train>")
        print("   or: kg align --domain <dfc|dpi|accounting|foreclosure|…> --train <mfi_integration_vX.Y.Z>")
        raise SystemExit(2)
    wm=_load_watermark() or {}
    repos=wm.get("repos") or {}
    bad=[]
    print(f"ALIGN check (KG built {wm.get('built_at','?')}):")
    for r,b in expectations:
        info=repos.get(r) or {}
        got=info.get("branch")
        live=_git(os.path.join(ROOT,r),"rev-parse","--abbrev-ref","HEAD")
        ok = (got==b) and (not live or live==b)
        mark="OK" if ok else "FAIL"
        print(f"  [{mark}] {r}: expect={b}  kg_watermark={got or '?'}  live={live or '?'}")
        if not ok:
            bad.append(r)
    if bad:
        print("MISALIGNED — run:")
        print(f"  bash scripts/bin/sync-branches.sh --domain {domain or 'accounting'} --train {train or branch} --yes")
        print("  bash scripts/bin/kg-switch.sh --force")
        print("Then re-run: kg align …")
        raise SystemExit(2)
    print("ALIGNED — safe to use kg impact/flow/orient for this train (still verify orch+Java).")


def _orient_verify_paths(c, query):
    """Source-of-truth paths for runtime verification — orch XML, processors, money tables."""
    nid = resolve(c, query) or resolve(c, "request:" + query)
    if not nid or not str(nid).startswith("request:"):
        return
    orch = sorted({e[0] for e in c.execute(
        "SELECT DISTINCT src FROM edges WHERE src_id=? AND rel='invokes' AND src IS NOT NULL", (nid,)
    ).fetchall() if e[0]})
    procs = sorted({e[0].split(":", 1)[-1] for e in c.execute(
        "SELECT DISTINCT dst_id FROM edges WHERE src_id=? AND rel='invokes'", (nid,)
    ).fetchall()})
    nested = sorted({e[0] for e in c.execute(
        "SELECT DISTINCT dst_id FROM edges WHERE src_id=? AND rel='calls'", (nid,)
    ).fetchall()})
    writes = set()
    proc_ids = [r[0] for r in c.execute(
        "SELECT DISTINCT dst_id FROM edges WHERE src_id=? AND rel='invokes'", (nid,)
    ).fetchall()]
    if proc_ids:
        qm2 = ",".join("?" * len(proc_ids))
        for row in c.execute(
            f"SELECT DISTINCT dst_id FROM edges WHERE rel='writes' AND src_id IN ({qm2})",
            proc_ids,
        ).fetchall():
            writes.add(row[0].split(":", 1)[-1])
    print("--- verify (source-of-truth — KG index only; confirm in live orch/Java/DB) ---")
    if orch:
        print(f"  orch XML ({len(orch)}):")
        for p in orch[:12]:
            print(f"    {p}")
        if len(orch) > 12:
            print(f"    … +{len(orch) - 12} more")
    if procs:
        print(f"  processors ({len(procs)}): {', '.join(procs[:8])}" + (" …" if len(procs) > 8 else ""))
    if nested:
        print(f"  nested requests: {', '.join(n.split(':', 1)[-1] for n in nested)}")
    if writes:
        print(f"  assert tables (write-set): {', '.join(sorted(writes)[:10])}" + (" …" if len(writes) > 10 else ""))
    print("  runtime: read orch XML above → grep processor .java → db-query canned SQL on assert tables")


def cmd_orient(c,a):
    """Evidence-only map for a request: flow spine + why surface + cases. Does not invent edges."""
    a=_pop_require_align(a)
    brief=False
    if "--brief" in a:
        brief=True
        a=[x for x in a if x!="--brief"]
    if not a:
        print("Usage: kg orient <request> [--brief] [--require-repo R --require-branch B]  — flow + why + cases"); return
    # Record orient timestamp for orient-before-edit gate (X4).
    _touch_orient_session(a[0] if a else "")
    print("=== ORIENT (evidence only — verify orch XML + DB before claiming) ===")
    wm=_load_watermark() or {}
    acc=(wm.get("repos") or {}).get("trustt-platform-accounting") or {}
    if acc:
        print(f"--- kg train: accounting={acc.get('branch','?')}@{acc.get('sha','?')} "
              f"WIP — use `kg align --repo trustt-platform-accounting --branch <train>` before money claims ---")
    _pop_require_align._nested = True  # type: ignore[attr-defined]
    try:
        print("--- flow ---")
        if brief:
            cmd_flow._brief_cap = 20  # type: ignore[attr-defined]
        try:
            cmd_flow(c,a)
        finally:
            cmd_flow._brief_cap = None  # type: ignore[attr-defined]
        print("--- why (silent failure surface) ---")
        prev_cap = getattr(cmd_why, "_auto_cap", None)
        if brief:
            cmd_why._auto_cap = 5  # type: ignore[attr-defined]
        try:
            cmd_why(c,a)
        finally:
            if brief:
                cmd_why._auto_cap = prev_cap  # type: ignore[attr-defined]
        print("--- cases (CHANGELOG precedents only) ---")
        cmd_cases(c,a)
        _orient_verify_paths(c, a[0])
    finally:
        _pop_require_align._nested = False  # type: ignore[attr-defined]



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

def _pop_fetch_if_stale(a):
    """Pull --fetch-if-stale from argv for fixed-elsewhere."""
    fetch = False
    rest = []
    i = 0
    while i < len(a):
        if a[i] == "--fetch-if-stale":
            fetch = True
            i += 1
        else:
            rest.append(a[i])
            i += 1
    return fetch, rest


def cmd_fixed_elsewhere(c,a):
    """Delegate cross-branch lookup; KG remains the evidence source for flow files/case SHAs."""
    if not a:
        print("Usage: kg fixed-elsewhere <apiName|processor|path|sha> [--repo R] [--base B] [--fetch-if-stale]"); return
    fetch_if_stale, a = _pop_fetch_if_stale(a)
    import subprocess
    root=os.path.abspath(os.path.join(HERE,"../../.."))
    tool=os.path.join(root,"scripts","lib","branch_train.py")
    cmd = [sys.executable, tool, "fixed-elsewhere", *a]
    if fetch_if_stale:
        cmd.append("--fetch-if-stale")
    # Capture stdout — MCP stdio must stay JSON-RPC-only (never inherit fd1).
    p=subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    if p.stdout:
        print(p.stdout, end="" if p.stdout.endswith("\n") else "\n")
    if p.returncode:
        raise SystemExit(p.returncode)

def cmd_schema(c,a):
    """Structure + code binding + train label for a table or column.

    Not a KG read — the oracle is generated from the live DB and the Java tree, so
    this serves without a KG rebuild.
    """
    if not a: print("usage: kg schema <table>[.<column>]"); return
    ws=Path(__file__).resolve().parents[3]
    sys.path.insert(0,str(ws/"scripts"/"lib"))
    import schema_oracle, column_binding
    ref=a[0]
    print(schema_oracle.describe(ref))
    if "." in ref:
        print(column_binding.describe(ref))
        diff=ws/"cursor-bundle"/"schema"/"train-diff.json"
        if diff.is_file():
            data=json.loads(diff.read_text(encoding="utf-8"))
            if ref in set(data.get("local_only_columns") or []):
                print(f"  TRAIN    local-only — no migration on initial-setup@{data.get('flyway_branch')}; "
                      "do not build a cross-train contract on it")

CMDS={"stats":cmd_stats,"search":cmd_search,"node":cmd_node,"flow":cmd_flow,"deps":cmd_deps,
      "schema":cmd_schema,
      "docs":cmd_docs,"neighbors":cmd_neighbors,"impact":cmd_impact,"path":cmd_path,"sql":cmd_sql,
      "cases":cmd_cases,"table":cmd_table,"concept":cmd_concept,"error":cmd_error,"why":cmd_why,"config":cmd_why,"doctor":cmd_doctor,"stale":cmd_stale,
      "watermark":cmd_watermark,"crud":cmd_crud,"writes":cmd_writes,"reads":cmd_reads,"deletes":cmd_deletes,
      "fresh":cmd_fresh,"validate":cmd_validate,"orient":cmd_orient,"align":cmd_align,
      "fixed-elsewhere":cmd_fixed_elsewhere}

# Commands that READ knowledge (must be branch-correct). doctor/watermark/stats report drift
# themselves, so they're excluded to avoid a double banner.
_KNOWLEDGE_CMDS={"search","node","flow","deps","docs","neighbors","impact","path","sql",
                 "cases","table","concept","error","why","config","crud","writes","reads","deletes",
                 "orient","fixed-elsewhere"}
# align is intentionally NOT auto-rebuilding — it reports watermark mismatch for a named train

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
