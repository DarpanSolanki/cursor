#!/usr/bin/env python3
"""
build_orchestration.py — extract the Request -> Processor flow spine from the
platform orchestration XMLs into KG node/edge JSONL.

Deterministic, provenance-tagged. No external deps (stdlib only).

Request ids are repo-scoped to avoid cross-service collisions (Upgrade 10):
  id = request:{repo}/{name}   label = name

Processor beans stay processor:{bean} (Spring bean id); repo on the node is set
from the orch file emitting it. Shared bean names across services are marked
repo=shared in a build.sh post-pass when multi-repo.

Usage: build_orchestration.py <repoDir> [<repoDir> ...]   -> JSONL on stdout
"""
import sys, os, re, json, glob

# Allow spaces around =  (notifications/LOS: name = "foo")
REQ_RE   = re.compile(r'<Request\s+[^>]*\bname\s*=\s*"([^"]+)"')
PROC_RE  = re.compile(r'<Processor\s+[^>]*\bbean\s*=\s*"([^"]+)"')
CTRL_RE  = re.compile(r'<Control\b[^>]*>')
CTRL_FC  = re.compile(r'pattern="\$\{function_code\}"[^>]*value="([^"]+)"')
CTRL_CLOSE = re.compile(r'</Control>')
REQ_CLOSE  = re.compile(r'</Request>')
API_RE   = re.compile(r'<API\s+([^>]*)/?>')
ATTR_RE  = re.compile(r'(\w+)="([^"]*)"')

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

def repo_name(p):
    parts = os.path.abspath(p).split(os.sep)
    for seg in parts:
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(p.rstrip(os.sep))

def req_id(repo, name):
    return f"request:{repo}/{name}"

def process_file(path, repo):
    rel = os.path.relpath(path, start=os.getcwd())
    cur_req = None
    cur_req_id = None
    seq = 0
    ctrl_stack = []
    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            m = REQ_RE.search(line)
            if m:
                cur_req = m.group(1)
                cur_req_id = req_id(repo, cur_req)
                seq = 0
                ctrl_stack = []
                emit({"t":"node","id":cur_req_id,"kind":"request",
                      "label":cur_req,"repo":repo,"src":f"{rel}:{lineno}"})
                continue
            if cur_req is None:
                continue
            for cm in CTRL_RE.finditer(line):
                fc = CTRL_FC.search(cm.group(0))
                ctrl_stack.append(fc.group(1) if fc else None)
            for _ in CTRL_CLOSE.finditer(line):
                if ctrl_stack: ctrl_stack.pop()
            pm = PROC_RE.search(line)
            if pm:
                bean = pm.group(1)
                seq += 1
                cond = next((c for c in reversed(ctrl_stack) if c), "*")
                emit({"t":"node","id":f"processor:{bean}","kind":"processor",
                      "label":bean,"repo":repo,"src":f"{rel}:{lineno}"})
                emit({"t":"edge","from":cur_req_id,"to":f"processor:{bean}",
                      "rel":"invokes","seq":seq,"cond":cond,"repo":repo,"src":f"{rel}:{lineno}"})
            am = API_RE.search(line)
            if am:
                attrs = dict(ATTR_RE.findall(am.group(1)))
                name = attrs.get("name") or attrs.get("uri") or attrs.get("method") or "api"
                api_id = f"api:{name}"
                emit({"t":"node","id":api_id,"kind":"api","label":name,"repo":repo,
                      "src":f"{rel}:{lineno}","attrs":attrs})
                emit({"t":"edge","from":cur_req_id,"to":api_id,
                      "rel":"calls_api","repo":repo,"src":f"{rel}:{lineno}"})
            if REQ_CLOSE.search(line):
                cur_req = None
                cur_req_id = None

def orchestration_xmls(repo_dir):
    """Any XML under an orchestration/ dir (or *_orc.xml anywhere) that actually
    holds <Request> definitions."""
    cands = set(glob.glob(os.path.join(repo_dir, "**", "*_orc.xml"), recursive=True))
    cands |= set(glob.glob(os.path.join(repo_dir, "**", "orchestration", "**", "*.xml"), recursive=True))
    out = []
    for f in cands:
        if "/build/" in f or "/.git/" in f:
            continue
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                head = fh.read(200000)
            if "<Request" in head and "name" in head:
                out.append(f)
        except OSError:
            pass
    return sorted(out)

def main():
    for repo_dir in sys.argv[1:]:
        repo = repo_name(repo_dir)
        for xml in orchestration_xmls(repo_dir):
            process_file(xml, repo)

if __name__ == "__main__":
    main()
