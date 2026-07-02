#!/usr/bin/env python3
"""
build_failuremodes.py — the FAILURE-SURFACE layer: map, for EVERY in-flow processor
AND the service/helper classes it uses, the silent decision-points where bugs hide.

The reads/writes graph shows STRUCTURE; it can't see WHERE a flow silently produces a
wrong/zero/empty/missing result. Those live in a handful of code shapes that recur
platform-wide:

  • silent_catch   — catch block that returns/continues WITHOUT rethrowing (swallowed failure)
  • zero_default   — return BigDecimal.ZERO / "0.00" / new BigDecimal(0) / orElse(ZERO) / ec.put(x,"0.00")
  • null_default   — return null
  • empty_default  — return Collections.emptyList() / new ArrayList<>()

For EACH such class it emits one `diag` node (class=silent_failure_surface) with exact
file:line points, and links the surface into every flow that can reach it:

    processor:<bean>        -[has_failure_mode]->  diag:auto.<Processor>      (its own surface)
    processor:<bean>        -[has_failure_mode]->  diag:auto.<Service/Helper>  (an injected dep's surface)

So `kg why <request>` walks request -invokes-> processors -> {own + injected} surfaces:
every flow's compute logic is covered, no per-flow hand-authoring. Curated diags
(diagnostics.jsonl) add verified root-causes + live SQL on top.

Usage: build_failuremodes.py <accumulated_raw.jsonl> <repoDir> [<repoDir> ...]
"""
import os, re, sys, glob, json

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")
def warn(*a): print(*a, file=sys.stderr)

KNOWN_PROC=set()
def load_known(tmp):
    for line in open(tmp, encoding="utf-8", errors="replace"):
        try: o=json.loads(line)
        except Exception: continue
        if o.get("t")=="node" and o.get("kind")=="processor":
            KNOWN_PROC.add(o["id"][len("processor:"):])

def bean_name(cls):
    if len(cls)>1 and cls[0].isupper() and cls[1].isupper(): return cls
    return cls[0].lower()+cls[1:] if cls else cls

def strip_comments(txt):
    txt=re.sub(r'/\*.*?\*/', ' ', txt, flags=re.S)
    txt=re.sub(r'//[^\n]*', ' ', txt)
    return txt

CLASS_RE=re.compile(r'\b(?:class|interface)\s+([A-Z]\w*)')
ZERO=re.compile(r'return\s+BigDecimal\.ZERO\b'
                r'|return\s+(?:new\s+)?BigDecimal\(\s*"?0(?:\.0+)?"?\s*\)'
                r'|BigDecimal\.valueOf\(\s*0\s*[L)]'
                r'|return\s+"0(?:\.0+)?"\s*;'
                r'|\.orElse\(\s*BigDecimal\.ZERO\s*\)'
                r'|\.put(?:Local)?\([^,;]+,\s*"0(?:\.0+)?"'
                r'|\.put(?:Local)?\([^,;]+,\s*BigDecimal\.ZERO')
NULL=re.compile(r'return\s+null\s*;|\.orElse\(\s*null\s*\)')
EMPTY=re.compile(r'return\s+Collections\.empty\w*\(\s*\)'
                 r'|return\s+new\s+(?:ArrayList|LinkedList|HashMap|HashSet)\s*<'
                 r'|\.orElse\(\s*Collections\.empty')
CATCH=re.compile(r'catch\s*\(')
# injected dependency field types in a processor (service/helper/util that hold compute logic)
DEP_FIELD=re.compile(r'(?:@Autowired\s+|@Inject\s+|private\s+|protected\s+|public\s+|final\s+)+'
                     r'([A-Z]\w*(?:Service|Helper|Util|Manager|Resolver|Calculator|Strategy))\b(?:<[^;=]*>)?\s+\w+\s*;')

CAP=30

def line_at(text, pos): return text.count('\n', 0, pos)+1

def silent_catches(text):
    out=[]
    for m in CATCH.finditer(text):
        b=text.find('{', m.end())
        if b<0: continue
        d=1; j=b+1; n=len(text)
        while j<n and d>0:
            ch=text[j]
            if ch=='{': d+=1
            elif ch=='}': d-=1
            j+=1
        body=text[b+1:j-1]
        if ('throw' not in body) and re.search(r'\b(return|continue)\b', body):
            out.append(line_at(text, m.start()))
    return out

def scan(path):
    raw=open(path, encoding="utf-8", errors="replace").read()
    if "class " not in raw and "interface " not in raw: return None, [], set()
    cm=CLASS_RE.search(raw)
    if not cm: return None, [], set()
    txt=strip_comments(raw)
    pts=[]
    for ln_no, line in enumerate(txt.splitlines(), 1):
        if ZERO.search(line):   pts.append((ln_no,"zero_default"))
        elif NULL.search(line): pts.append((ln_no,"null_default"))
        elif EMPTY.search(line):pts.append((ln_no,"empty_default"))
    for ln in silent_catches(txt): pts.append((ln,"silent_catch"))
    pts.sort()
    deps={m.group(1) for m in DEP_FIELD.finditer(txt)}
    return cm.group(1), pts, deps

def main():
    tmp=sys.argv[1]; repos=sys.argv[2:]
    load_known(tmp)
    files=[]
    for rd in repos:
        for pat in ("*Processor.java","*Service.java","*Helper.java","*Util.java",
                    "*Manager.java","*Resolver.java","*Calculator.java"):
            files+=glob.glob(os.path.join(rd,"src","main","java","**",pat), recursive=True)
    files=sorted(set(files))
    # pass 1: per-class silent surface + processor dep types
    surface={}     # ClassName -> (relpath, points, summary)
    proc_deps={}   # proc ClassName -> set(dep type names)
    for jf in files:
        cls, pts, deps = scan(jf)
        if not cls: continue
        rel=os.path.relpath(jf, start=os.getcwd())
        if pts and cls not in surface:
            by={}
            for _,k in pts: by[k]=by.get(k,0)+1
            summary=", ".join(f"{k}×{v}" for k,v in sorted(by.items()))
            surface[cls]=(rel, pts, summary)
        if cls.endswith("Processor"): proc_deps[cls]=deps
    # pass 2: emit nodes for classes reachable from an in-flow processor (proc itself, or injected dep)
    emitted=set(); nproc=0; nlinked=0
    def emit_node(cls):
        if cls in emitted or cls not in surface: return
        rel, pts, summary = surface[cls]
        points=[f"{rel}:{ln} ({k})" for ln,k in pts[:CAP]]
        emit({"t":"node","id":f"diag:auto.{cls}","kind":"diag","class":"silent_failure_surface",
              "label":f"{cls} — silent-failure surface ({summary})",
              "role":f"{cls} silent failure surface return zero null empty catch swallow default decision point {summary}",
              "src":rel,"surface":summary,"points":points,
              "note":"auto-extracted candidate silent branches; a wrong/0/missing/empty result here most likely fires one of these — confirm with the flow's live data."})
        emitted.add(cls)
    for cls, deps in proc_deps.items():
        bean=bean_name(cls)
        if bean not in KNOWN_PROC: continue
        nproc+=1
        targets=[t for t in [cls, *sorted(deps)] if t in surface]
        for t in targets: emit_node(t)
        for t in targets:
            emit({"t":"edge","from":f"processor:{bean}","to":f"diag:auto.{t}","rel":"has_failure_mode",
                  "note":surface[t][2],"src":surface[t][0]})
            nlinked+=1
    warn(f"[failuremodes] in-flow processors scanned={nproc}, surface nodes emitted={len(emitted)}, links={nlinked}")

if __name__=="__main__": main()
