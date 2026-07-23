#!/usr/bin/env python3
"""
build_dataaccess.py — fold the DB-access (CRUD) layer into the system KG.

For every processor, statically resolve the database operations it performs by
walking the real data-access chain in this platform:

    Processor  --@Autowired-->  DAOService / helper  -->  Repository(JpaRepository<Entity>)
                                                          -->  @Entity(@Table name="...")

and emits edges:

    processor:<bean>  -[reads | writes | deletes]->  table:<name>
        json = {op, via, src}     # op = fine operation, via = resolved chain, src = processor call-site file:line

`op` (fine):  read | count | exists | create | update | upsert | delete |
              soft_delete | native_select | native_insert | native_update | native_delete
Coarse rel:   read/count/exists/native_select        -> reads
              create/update/upsert/insert/soft_delete/native_insert/native_update -> writes
              delete/native_delete                    -> deletes

Resolution sources, in priority order, per method:
  1. @Query / @Modifying SQL (native real table names, or JPQL entity names) — most precise.
  2. Spring-Data built-ins (save/findById/deleteById/...) + derived query names (findBy/deleteBy/...).
  3. Method-body field.method() calls walked recursively (DAO -> repo, processor -> helper -> DAO).
  4. Fallback: entity type in the method signature + op from the method-name prefix.

Only edges whose processor:<bean> AND table:<name> already exist as nodes in the
accumulated graph ($tmp) are emitted — nothing dangles, no duplicate nodes.
Deterministic, stdlib-only. Unresolved call sites are logged to stderr (counted).

Usage: build_dataaccess.py <accumulated_raw.jsonl> <repoDir> [<repoDir> ...]
"""
import os, re, sys, glob, json, collections

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
def warn(*a): print(*a, file=sys.stderr)

# ---- node universe already in the graph (from orchestration + tables passes) ----
KNOWN_PROC=set()   # bean names (without "processor:" prefix)
KNOWN_TABLE=set()  # table names (without "table:" prefix)
def load_known(tmp):
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try: o=json.loads(line)
        except Exception: continue
        if o.get("t")!="node": continue
        if o.get("kind")=="processor": KNOWN_PROC.add(o["id"][len("processor:"):])
        elif o.get("kind")=="table":   KNOWN_TABLE.add(o["id"][len("table:"):])

# ---- bean name from class (Spring AnnotationBeanNameGenerator) ----
def bean_name(cls):
    if len(cls)>1 and cls[0].isupper() and cls[1].isupper(): return cls   # e.g. URLProcessor stays as-is
    return cls[0].lower()+cls[1:] if cls else cls

# ---- light comment stripper (keeps string literals so @Query SQL survives) ----
def strip_comments(txt):
    txt=re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    txt=re.sub(r'//[^\n]*', ' ', txt)
    return txt

REPO_BASE=re.compile(r'extends\s+[\w.]*Repository\s*<\s*([A-Za-z_]\w*)')   # any *Repository<Entity> base incl. custom (IAccountRepository<LoanAccountEntity>)
TABLE_RE=re.compile(r'@Table\s*\(\s*name\s*=\s*"([^"]+)"')
CLASS_RE=re.compile(r'\b(?:class|interface)\s+([A-Z]\w*)')
ENTITY_DECL=re.compile(r'@Entity\b')
AUTOWIRED=re.compile(r'@(?:Autowired|Inject)\b')
# a field declaration line:  [final] TypeName fieldName ;    (TypeName starts uppercase)
FIELD_RE=re.compile(r'^\s*(?:final\s+)?([A-Z]\w*)(?:<[^;=]*>)?\s+(\w+)\s*;')
CALL_RE=re.compile(r'\b([a-z_]\w*)\s*\.\s*(\w+)\s*\(')    # field.method( — tolerates newline-wrapped fluent calls
BARE_RE=re.compile(r'(?:^|[^.\w])([a-z_]\w*)\s*\(')       # bare name( — candidate intra-class call (not a member access)
_KW={'if','for','while','switch','catch','return','new','else','do','synchronized','try',
     'throw','assert','instanceof','super','this','case','break','continue'}
QUERY_RE=re.compile(r'@Query\s*\(\s*(?:nativeQuery\s*=\s*(true|false)\s*,\s*)?value\s*=\s*("(?:[^"\\]|\\.)*"(?:\s*\+\s*"(?:[^"\\]|\\.)*")*)', re.S)
QUERY_SIMPLE=re.compile(r'@Query\s*\(\s*("(?:[^"\\]|\\.)*"(?:\s*\+\s*"(?:[^"\\]|\\.)*")*)', re.S)
MODIFYING=re.compile(r'@Modifying\b')
METHOD_SIG=re.compile(r'(\w+)\s*\(')                       # crude method-name grab
INLINE_SQL=re.compile(r'create(?:Native)?Query\s*\(\s*("(?:[^"\\]|\\.)*"(?:\s*\+\s*"(?:[^"\\]|\\.)*")*)', re.S)

def cat_strings(lit):
    # join "a" + "b" + ... -> a b
    parts=re.findall(r'"((?:[^"\\]|\\.)*)"', lit)
    return " ".join(p.replace('\\n',' ').replace('\\"','"') for p in parts)

def sql_op_tables(sql, entity2tbl):
    s=re.sub(r'\s+',' ',sql).strip().lower()
    verb=None
    for v in ("insert","update","delete","select","with"):
        if s.startswith(v): verb=v; break
    if verb=="with":   # CTE — find first real verb
        for v in ("insert","update","delete","select"):
            if v in s: verb=v; break
    raw=set()
    for m in re.finditer(r'\b(?:from|join|into|update)\s+([a-z_][a-z0-9_\.]*)', s):
        t=m.group(1).split('.')[-1]
        raw.add(t)
    tables=set()
    for t in raw:
        if t in KNOWN_TABLE: tables.add(t)
        elif t in entity2tbl: tables.add(entity2tbl[t])
        # else: alias/cte/unknown -> dropped (logged by caller)
    soft = verb=="update" and ("is_deleted" in s or "isdeleted" in s)
    op={"select":"native_select","insert":"native_insert","delete":"native_delete",
        "update":"soft_delete" if soft else "native_update"}.get(verb)
    return op, tables, raw

# op classification from a method name prefix (derived-query / DAO convention)
def op_from_name(m):
    n=m.lower()
    if n.startswith(("save","persist","insert","add","create","store","upsert")): return "upsert"
    if n.startswith(("delete","remove","purge")): return "delete"
    if n.startswith(("update","modify","patch","set")) or "update" in n: return "update"
    # write-ish domain verbs (state mutations that aren't named save/update): mark paid, book interest, post txn, settle, etc.
    if n.startswith(("mark","book","post","settle","apply","void","cancel","close","expire","release",
                     "reverse","adjust","increment","decrement","activate","deactivate","assign","unassign",
                     "lock","unlock","approve","reject","sync","bulkupdate")): return "update"
    if n.startswith(("find","get","fetch","load","list","read","select","search","count","exist","is","has","retrieve","check")):
        return "count" if n.startswith("count") else ("exists" if n.startswith(("exist","is","has")) else "read")
    return None

BUILTIN={"save":"upsert","saveall":"upsert","saveandflush":"upsert",
         "findbyid":"read","findall":"read","findallbyid":"read","getone":"read","getbyid":"read",
         "existsbyid":"exists","count":"count","delete":"delete","deletebyid":"delete",
         "deleteall":"delete","deleteallbyid":"delete","deleteinbatch":"delete"}

def op_to_rel(op):
    if op in ("read","count","exists","native_select"): return "reads"
    if op in ("delete","native_delete"): return "deletes"
    return "writes"   # create/update/upsert/insert/soft_delete/native_*

# ---- per-class parsed model ----
class Cls:
    __slots__=("name","kind","file","entity","fields","methods","is_repo","repo_methods","implements")
    def __init__(s,name,kind,file):
        s.name=name; s.kind=kind; s.file=file
        s.entity=None; s.fields={}; s.methods={}; s.is_repo=False
        s.repo_methods={}      # repo: method_lower -> (op, frozenset(tables))
        s.implements=[]        # interfaces this class implements (for interface-typed field resolution)

# brace-aware method body extraction (returns list of (name, body, start_line))
def methods_of(txt):
    out=[]; i=0; n=len(txt); depth=0; line=1
    # find class body open brace first
    # iterate, when depth==1 and we see a method signature ending with '{', capture to matching '}'
    sig_start=None
    while i<n:
        ch=txt[i]
        if ch=='\n': line+=1
        if ch=='{':
            if depth==1:
                # look back for a signature on this brace
                head=txt[max(0,i-400):i]
                mm=re.search(r'(?:public|protected|private|static|final|synchronized|\s)[\w<>\[\],\.\?\s]*?\b(\w+)\s*\([^;{}]*\)\s*(?:throws [\w\.,\s]+)?\s*$', head)
                # capture body
                d=1; j=i+1; bl=line
                while j<n and d>0:
                    if txt[j]=='{': d+=1
                    elif txt[j]=='}': d-=1
                    elif txt[j]=='\n': line+=1
                    j+=1
                if mm:
                    out.append((mm.group(1), txt[i+1:j-1], bl))
                i=j; depth=depth  # depth unchanged (we consumed the balanced body)
                continue
            depth+=1
        elif ch=='}':
            depth-=1
        i+=1
    return out

def parse_class(path, entity2tbl, repo_entity):
    raw=open(path, encoding="utf-8", errors="replace").read()
    if "class " not in raw and "interface " not in raw: return None
    cm=CLASS_RE.search(raw)
    if not cm: return None
    name=cm.group(1)
    kind="interface" if re.search(r'\binterface\s+'+name, raw) else "class"
    c=Cls(name, kind, path)
    # repository?
    rb=REPO_BASE.search(raw)
    if rb and kind=="interface":
        c.is_repo=True; c.entity=rb.group(1)
    # implemented interfaces (so a call on an interface-typed field resolves to the impl)
    im=re.search(r'\bclass\s+'+re.escape(name)+r'\b[^{]*?\bimplements\s+([\w,\s\.<>]+?)\s*\{', raw, re.S)
    if im:
        for t in re.findall(r'\b([A-Z]\w*)', im.group(1)):
            if t not in c.implements: c.implements.append(t)
    txt=strip_comments(raw)
    # autowired fields
    lines=txt.splitlines()
    for idx,ln in enumerate(lines):
        if AUTOWIRED.search(ln):
            for look in range(idx, min(idx+4, len(lines))):
                fm=FIELD_RE.match(lines[look])
                if fm:
                    c.fields[fm.group(2)]=fm.group(1); break
    # also pick up plainly-declared injected fields of *DAOService/*Repository even without @Autowired on same scan
    for fm in re.finditer(r'^\s*(?:@\w+\s+)*(?:private|protected|public)?\s*(?:final\s+)?([A-Z]\w*(?:DAOService|DaoService|Repository|Helper|Manager|Service))\s+(\w+)\s*;', txt, re.M):
        c.fields.setdefault(fm.group(2), fm.group(1))

    if c.is_repo:
        # parse declared methods + their @Query/@Modifying; build repo_methods map
        ent=c.entity
        tbl=entity2tbl.get(ent.lower()) if ent else None
        base_tbls=frozenset([tbl]) if tbl in KNOWN_TABLE else frozenset()
        # built-ins
        for bn,op in BUILTIN.items(): c.repo_methods[bn]=(op, base_tbls)
        # walk interface body method decls (end with ';'), with preceding annotations
        decls=re.split(r';', raw)
        for seg in decls:
            mods="@Modifying" in seg
            qy=QUERY_RE.search(seg) or QUERY_SIMPLE.search(seg)
            # method name = last identifier before '(' in this segment
            nm=None
            for mm in re.finditer(r'\b(\w+)\s*\(', seg): nm=mm.group(1)
            if not nm: continue
            if qy:
                lit=qy.group(2) if qy.re is QUERY_RE else qy.group(1)
                op,tbls,raws=sql_op_tables(cat_strings(lit), entity2tbl)
                if op:
                    c.repo_methods[nm.lower()]=(op, frozenset(tbls) or base_tbls)
                    continue
            # derived query
            op=op_from_name(nm) or "read"
            c.repo_methods[nm.lower()]=(op, base_tbls)
        return c

    # normal class: capture method bodies + signature entities
    for mname, body, bl in methods_of(txt):
        calls=[(fm.group(1), fm.group(2)) for fm in CALL_RE.finditer(body)]
        bare=[bm.group(1) for bm in BARE_RE.finditer(body) if bm.group(1) not in _KW]
        # inline SQL in body
        inline=[]
        for q in INLINE_SQL.finditer(body):
            op,tbls,_=sql_op_tables(cat_strings(q.group(1)), entity2tbl)
            if op and tbls: inline.append((op, frozenset(tbls)))
        # does this body actually touch the DB? (distinguishes a real miss from a no-DB helper)
        hasdb=bool(re.search(r'Repository\s*\.\s*\w+\s*\(|create(?:Native)?Query|@Query|\.save\s*\(|'
                             r'\.saveAll\s*\(|\.persist\s*\(|\.merge\s*\(|\.delete\w*\s*\(|jdbcTemplate', body))
        c.methods.setdefault(mname, []).append({"calls":calls, "inline":inline, "bare":bare, "hasdb":hasdb, "line":bl})
    return c

# ---- resolution across the class graph ----
def build_index(repos):
    # entity simple-name(lower) -> table  (authoritative from @Table)
    entity2tbl={}
    files=[]
    for rd in repos:
        for jf in glob.glob(os.path.join(rd,"src","main","java","**","*.java"), recursive=True):
            files.append(jf)
    # first pass: entity->table + repo entities
    for jf in files:
        try: raw=open(jf,encoding="utf-8",errors="replace").read()
        except OSError: continue
        if "@Table" in raw and "@Entity" in raw:
            cm=CLASS_RE.search(raw); tm=TABLE_RE.search(raw)
            if cm and tm: entity2tbl[cm.group(1).lower()]=tm.group(1)
    return files, entity2tbl

def main():
    tmp=sys.argv[1]; repos=sys.argv[2:]
    load_known(tmp)
    files, entity2tbl = build_index(repos)
    classes={}   # simple name -> Cls
    for jf in files:
        try:
            c=parse_class(jf, entity2tbl, None)
        except Exception as e:
            warn(f"parse-fail {jf}: {e}"); continue
        if not c: continue
        if c.name in classes:                 # simple-name collision (e.g. HolidayDAOService in 2 repos) -> MERGE, don't overwrite
            ex=classes[c.name]
            for k,insts in c.methods.items(): ex.methods.setdefault(k,[]).extend(insts)
            for k,v in c.fields.items(): ex.fields.setdefault(k,v)
            for k,v in c.repo_methods.items(): ex.repo_methods.setdefault(k,v)
            for i in c.implements:
                if i not in ex.implements: ex.implements.append(i)
            if c.is_repo and not ex.is_repo: ex.is_repo=True; ex.entity=ex.entity or c.entity
        else:
            classes[c.name]=c

    # interface -> implementing class (for interface-typed DAO fields: IDocumentFileDAOService -> impl)
    impl_of={}
    for nm,c in classes.items():
        if c.is_repo or not c.methods: continue
        for iface in c.implements:
            impl_of.setdefault(iface, nm)
    for nm in list(classes):   # convention fallback: interface IFoo -> class Foo
        if nm.startswith("I") and len(nm)>1 and nm[1].isupper():
            cand=nm[1:]
            if nm not in impl_of and cand in classes and classes[cand].methods: impl_of[nm]=cand

    memo={}
    INPROG=object()
    def resolve(clsname, mname, depth=0):
        """set of (op, table) the method performs, walking field.method calls."""
        key=(clsname, mname.lower())
        if key in memo:
            return set() if memo[key] is INPROG else memo[key]
        if depth>60: return set()   # safety net only; INPROG breaks real cycles. Must stay high:
                                    # a low limit truncates deep chains to empty AND memoizes that, poisoning the key.
        c=classes.get(clsname)
        if not c: return set()
        if c.is_repo:
            r=c.repo_methods.get(mname.lower())
            if r:
                op,tbls=r; return {(op,t) for t in tbls}
            # unknown repo method: a repo is always bound to its entity's table, so resolve to it
            # (op from the name; default read — the safest assumption for an unclassified accessor).
            op=op_from_name(mname) or "read"
            tbl=entity2tbl.get((c.entity or "").lower())
            return {(op,tbl)} if tbl in KNOWN_TABLE else set()
        memo[key]=INPROG
        res=set()
        insts=c.methods.get(mname, [])
        if not insts and clsname in impl_of:          # interface-typed field -> resolve via its impl
            res=resolve(impl_of[clsname], mname, depth+1)
            memo[key]=res; return res
        for inst in insts:
            for op,tbls in inst["inline"]:
                for t in tbls: res.add((op,t))
            for fld,meth in inst["calls"]:
                if fld=="this":                       # intra-class delegation (this.save -> save())
                    res|=resolve(clsname, meth, depth+1); continue
                ftype=c.fields.get(fld)
                if not ftype: continue
                res|=resolve(ftype, meth, depth+1)
            for nm2 in inst.get("bare",[]):           # bare intra-class call (getMappedQuestionnaireIdRaw())
                if nm2!=mname and nm2 in c.methods:
                    res|=resolve(clsname, nm2, depth+1)
        memo[key]=res
        return res

    TRACE=os.environ.get("KG_DA_TRACE")
    if TRACE:
        cn,_,mn=TRACE.partition(".")
        c=classes.get(cn)
        warn(f"[trace] {cn} in classes={bool(c)} is_repo={getattr(c,'is_repo',None)} entity={getattr(c,'entity',None)}")
        if c and not c.is_repo:
            warn(f"[trace] fields={c.fields}")
            warn(f"[trace] methods has '{mn}'={mn in c.methods}")
            for inst in c.methods.get(mn,[]): warn(f"[trace]   calls={inst['calls']} bare={inst.get('bare')} hasdb={inst.get('hasdb')}")
        if c and c.is_repo:
            warn(f"[trace] repo_methods['{mn.lower()}']={c.repo_methods.get(mn.lower())}")
            warn(f"[trace] entity2tbl[{(c.entity or '').lower()}]={entity2tbl.get((c.entity or '').lower())} in_KNOWN={entity2tbl.get((c.entity or '').lower()) in KNOWN_TABLE}")
        warn(f"[trace] resolve({TRACE}) = {resolve(cn, mn)}")

    DBG=os.environ.get("KG_DA_DEBUG")
    DBTYPE=("Repository","DAOService","DaoService","DAO","Dao")          # high-confidence data-access deps
    MAYBE=("Helper","Manager","Service","Util","Provider","Adapter")     # may reach the DB transitively
    def why_unresolved(ftype, meth):
        c=classes.get(ftype)
        if not c: return "type_not_parsed"
        if c.is_repo:
            if meth.lower() in c.repo_methods: return "repo_no_table"
            if op_from_name(meth) is None:     return "repo_name_unclassified"
            return "repo_entity_no_table"
        if meth not in c.methods: return "dao_method_not_captured"
        # real miss only if the body genuinely has DB access we failed to extract; else it's a no-DB helper
        return "dao_body_empty_REAL" if any(i.get("hasdb") for i in c.methods[meth]) else "no_db_helper"

    # ---- emit processor/writer -> table edges ----
    # Upgrade 10: also scan *Writer / *ItemWriter (batch writers were under-extracted).
    def is_data_actor(name):
        return name.endswith("Processor") or name.endswith("Writer") or name.endswith("ItemWriter")

    edges={}  # (bean, rel, table, op) -> src (first wins)
    unresolved=0; proc_seen=0; proc_with_db=0; real_miss=0; no_db_skip=0
    miss_tbl=collections.Counter()
    unres_detail=collections.Counter()   # (reason, ftype, method) -> count
    for name,c in classes.items():
        if not is_data_actor(name): continue
        bean=bean_name(name)
        is_writer = name.endswith("Writer") or name.endswith("ItemWriter")
        if bean not in KNOWN_PROC and not is_writer:
            continue
        # Writers not in orch: still emit a processor node so edges are not dangling
        if is_writer and bean not in KNOWN_PROC:
            emit({"t":"node","id":f"processor:{bean}","kind":"processor","label":bean,
                  "role":"batch_writer","src":os.path.relpath(c.file, start=os.getcwd())})
            KNOWN_PROC.add(bean)
        proc_seen+=1
        rel=os.path.relpath(c.file, start=os.getcwd())
        hits=set()
        # gather all field.method calls anywhere in the processor, with call-site line
        raw=strip_comments(open(c.file,encoding="utf-8",errors="replace").read())
        for ln_no, line in enumerate(raw.splitlines(), 1):
            for cm in CALL_RE.finditer(line):
                fld,meth=cm.group(1),cm.group(2)
                ftype=c.fields.get(fld)
                if not ftype: continue
                ops=resolve(ftype, meth)
                if not ops:
                    if ftype.endswith(DBTYPE):
                        unresolved+=1
                        why=why_unresolved(ftype,meth)
                        if why.endswith("REAL") or why.endswith("not_captured"): real_miss+=1   # genuine missed DB op
                        else: no_db_skip+=1                                                       # method does no DB — correctly no edge
                        if DBG: unres_detail[(why,ftype,meth)]+=1
                    elif DBG and ftype.endswith(MAYBE):
                        unres_detail[("maybe:"+why_unresolved(ftype,meth),ftype,meth)]+=1
                    continue
                for op,tbl in ops:
                    if not tbl: continue
                    if tbl not in KNOWN_TABLE:
                        miss_tbl[tbl]+=1; continue
                    relk=op_to_rel(op)
                    key=(bean,relk,tbl,op)
                    if key not in edges:
                        edges[key]=f"{rel}:{ln_no}"
                    hits.add(tbl)
        if hits: proc_with_db+=1

    for (bean,relk,tbl,op),src in sorted(edges.items()):
        emit({"t":"edge","from":f"processor:{bean}","to":f"table:{tbl}","rel":relk,
              "note":op,"src":src})   # note = fine op (read/upsert/soft_delete/native_*); rel = coarse reads/writes/deletes

    warn(f"[dataaccess] processors(in-flow)={proc_seen} with-db={proc_with_db} edges={len(edges)} "
         f"| DB-call-sites unresolved={unresolved}: real-misses={real_miss} "
         f"(genuine missed DB op), no-db-helpers={no_db_skip} (method does no DB — correctly no edge) "
         f"| missing_table_refs={sum(miss_tbl.values())} (distinct {len(miss_tbl)})")
    if miss_tbl:
        warn("  top unmapped table refs: "+", ".join(f"{t}({n})" for t,n in miss_tbl.most_common(10)))
    if DBG and unres_detail:
        byreason=collections.Counter()
        for (reason,ft,m),n in unres_detail.items(): byreason[reason]+=n
        warn("  [debug] unresolved by reason: "+", ".join(f"{r}={n}" for r,n in byreason.most_common()))
        warn("  [debug] top unresolved (reason | type.method | count):")
        for (reason,ft,m),n in unres_detail.most_common(400):
            if reason.endswith("REAL") or reason.endswith("not_captured"):
                warn(f"      {reason:28} {ft}.{m}  x{n}")

if __name__=="__main__": main()
