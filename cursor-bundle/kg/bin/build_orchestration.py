#!/usr/bin/env python3
"""
build_orchestration.py — extract the Request -> Processor flow spine from the
platform orchestration XMLs into KG node/edge JSONL.

Deterministic, provenance-tagged. No external deps (stdlib only).

For every <Request name="R"> in any *_orc.xml under the given repos, emit:
  node  request:R     (repo, file, line)
  node  processor:P   (for each <Processor bean="P">)
  edge  request:R -invokes-> processor:P   (seq=N, cond=<function_code value or "*">, src=file:line)
  node  api:NAME       (for <API ... name=.. or method/uri>)
  edge  request:R -calls_api-> api:NAME
The function_code condition is tracked via the enclosing
<Control ... pattern="${function_code}" ... value="V"> nesting.

Usage: build_orchestration.py <repoDir> [<repoDir> ...]   -> JSONL on stdout
"""
import sys, os, re, json, glob

REQ_RE   = re.compile(r'<Request\s+[^>]*name="([^"]+)"')
PROC_RE  = re.compile(r'<Processor\s+[^>]*bean="([^"]+)"')
CTRL_RE  = re.compile(r'<Control\b[^>]*>')
CTRL_FC  = re.compile(r'pattern="\$\{function_code\}"[^>]*value="([^"]+)"')
CTRL_CLOSE = re.compile(r'</Control>')
REQ_CLOSE  = re.compile(r'</Request>')
API_RE   = re.compile(r'<API\s+([^>]*)/?>')
ATTR_RE  = re.compile(r'(\w+)="([^"]*)"')

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

def repo_name(p):
    # the repo dir is the first path component under the workspace root
    parts = os.path.abspath(p).split(os.sep)
    for i, seg in enumerate(parts):
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(p.rstrip(os.sep))

def process_file(path, repo):
    rel = os.path.relpath(path, start=os.getcwd())
    cur_req = None
    seq = 0
    ctrl_stack = []   # list of (function_code_value or None)
    req_line = 0
    with open(path, encoding="utf-8", errors="replace") as fh:
        for lineno, line in enumerate(fh, 1):
            # close controls first if line has closers (rough but Controls are whole-line in these files)
            m = REQ_RE.search(line)
            if m:
                cur_req = m.group(1)
                seq = 0
                ctrl_stack = []
                req_line = lineno
                emit({"t":"node","id":f"request:{cur_req}","kind":"request",
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
                emit({"t":"edge","from":f"request:{cur_req}","to":f"processor:{bean}",
                      "rel":"invokes","seq":seq,"cond":cond,"repo":repo,"src":f"{rel}:{lineno}"})
            am = API_RE.search(line)
            if am:
                attrs = dict(ATTR_RE.findall(am.group(1)))
                name = attrs.get("name") or attrs.get("uri") or attrs.get("method") or "api"
                api_id = f"api:{name}"
                emit({"t":"node","id":api_id,"kind":"api","label":name,"repo":repo,
                      "src":f"{rel}:{lineno}","attrs":attrs})
                emit({"t":"edge","from":f"request:{cur_req}","to":api_id,
                      "rel":"calls_api","repo":repo,"src":f"{rel}:{lineno}"})
            if REQ_CLOSE.search(line):
                cur_req = None

def orchestration_xmls(repo_dir):
    """Any XML under an orchestration/ dir (or *_orc.xml anywhere) that actually
    holds <Request> definitions — covers los/payments/task/batch whose files are
    NOT named *_orc.xml (ServiceOrchestrationXML.xml, orc_collections.xml, ...)."""
    cands = set(glob.glob(os.path.join(repo_dir, "**", "*_orc.xml"), recursive=True))
    cands |= set(glob.glob(os.path.join(repo_dir, "**", "orchestration", "**", "*.xml"), recursive=True))
    out = []
    for f in cands:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                head = fh.read(200000)
            if "<Request name=" in head: out.append(f)
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
