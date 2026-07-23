#!/usr/bin/env python3
"""
build_docs.py — fold brain / digests / skills into doc nodes (Upgrade 10).

Paths via _paths.py (no hardcoded /home/darpan/darpan). Auto-link to requests
and tables named in the text (grep/word-boundary). Provenance = file path.

Usage: build_docs.py <existing-nodes.jsonl>
"""
import os, re, json, sys, glob
from pathlib import Path

# local import
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _paths import WORKSPACE, BRAIN, BUNDLE

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

request_by_label = {}  # label -> [ids]
table_labels = set()
service_repos = {}

if len(sys.argv) > 1:
    for line in open(sys.argv[1], encoding="utf-8"):
        o = json.loads(line)
        if o.get("t") != "node":
            continue
        if o["kind"] == "request":
            request_by_label.setdefault(o["label"], []).append(o["id"])
        elif o["kind"] == "table":
            table_labels.add(o["label"])
        elif o["kind"] == "service":
            service_repos[o.get("label") or o["id"].split(":", 1)[-1]] = o["id"]

# Prefer unique labels for auto-link; skip ultra-short noisy tokens
req_re = {
    name: re.compile(r"\b" + re.escape(name) + r"\b")
    for name in request_by_label
    if len(name) >= 6
}
tbl_re = {
    name: re.compile(r"\b" + re.escape(name) + r"\b")
    for name in table_labels
    if len(name) >= 5 and "_" in name  # table-ish
}

def title_of(path: Path) -> str:
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("# "):
                return line[2:].strip()[:120]
    except OSError:
        pass
    return path.name

DOC_ROOTS = [
    (BRAIN, "brain"),
    (WORKSPACE / ".cursor", "cursor"),
    (WORKSPACE / ".cursor" / "skills", "skills"),
    (WORKSPACE / "system_brain", "system_brain"),
]

SKIP_PARTS = ("/kg/data/", "/node_modules/", "/.git/")

docs = []
for root, tag in DOC_ROOTS:
    if not root.is_dir():
        continue
    for path in root.rglob("*.md"):
        s = str(path)
        if any(x in s for x in SKIP_PARTS):
            continue
        # skills: only topic files + SKILL.md under accounting-knowledge / architect
        if tag == "skills":
            if path.name not in ("SKILL.md",) and "accounting-knowledge" not in s and "architect-thinking" not in s:
                if "/accounting-knowledge/" not in s and "/architect-thinking/" not in s:
                    continue
        docs.append(path)

docs = sorted(set(docs))
for path in docs:
    try:
        rel = str(path.relative_to(WORKSPACE))
    except ValueError:
        rel = str(path)
    did = "doc:" + rel.replace("\\", "/")
    emit({"t": "node", "id": did, "kind": "doc", "label": title_of(path), "src": rel})
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        continue
    # link requests
    for name, rx in req_re.items():
        if name in text and rx.search(text):
            for rid in request_by_label[name]:
                emit({"t": "edge", "from": did, "to": rid, "rel": "mentions", "src": rel})
    for name, rx in tbl_re.items():
        if name in text and rx.search(text):
            emit({"t": "edge", "from": did, "to": f"table:{name}", "rel": "mentions", "src": rel})
    for repo, sid in service_repos.items():
        short = repo.replace("trustt-platform-", "").replace("novopay-platform-", "")
        if repo in text or (len(short) > 4 and short in text):
            emit({"t": "edge", "from": did, "to": sid, "rel": "mentions", "src": rel})

# Curated pipeline edges (still derived from known request labels)
def req_ids(label):
    return request_by_label.get(label, [])

for a, b in (("dpiAccrualCalculation", "dpiAccrualBooking"), ("dpiAccrualBooking", "dpiBilling")):
    for aid in req_ids(a):
        for bid in req_ids(b):
            emit({"t": "edge", "from": aid, "to": bid, "rel": "next", "src": "build_docs.py:dpic"})

for r in ("dpiAccrualCalculation", "dpiAccrualBooking", "dpiBilling"):
    for rid in req_ids(r):
        # link brain dpic doc if present
        for cand in (
            BRAIN / "dpic" / "04-dpic-flow.md",
            WORKSPACE / "cursor-bundle" / "brain" / "dpic" / "04-dpic-flow.md",
        ):
            if cand.is_file():
                rel = str(cand.relative_to(WORKSPACE))
                emit({"t": "edge", "from": "doc:" + rel.replace("\\", "/"), "to": rid,
                      "rel": "documents", "src": rel})
                break

# Authoritative flow docs (brain/flows) — documents edges when file exists
AUTHORITATIVE = {
    "cursor-bundle/brain/flows/disbursement-end-to-end.md": [
        "disburseLoan", "childLoanDisbursement", "loanDisbursementCancellation",
    ],
    "cursor-bundle/brain/flows/repayment-end-to-end.md": [
        "loanRepayment", "childLoanRepayment", "collectionLoanRepayment",
    ],
    "cursor-bundle/brain/flows/foreclosure-and-closure.md": [
        "loanForeclosure", "childLoanForeclosure", "loanDeathForeclosure",
        "cancelLoanForeclosure", "loanWriteoff",
    ],
    "cursor-bundle/brain/flows/loan-writeoff.md": ["loanWriteoff"],
    "cursor-bundle/brain/flows/post-manual-journal-entry.md": ["postManualJournalEntry"],
    "cursor-bundle/brain/flows/loan-death-foreclosure.md": ["loanDeathForeclosure"],
}
for doc, reqs in AUTHORITATIVE.items():
    p = WORKSPACE / doc
    if not p.is_file():
        continue
    did = "doc:" + doc
    for r in reqs:
        for rid in req_ids(r):
            emit({"t": "edge", "from": did, "to": rid, "rel": "documents", "src": doc})

# Promoted learning diags (api field) → has_failure_mode on matching requests
if len(sys.argv) > 1:
    for line in open(sys.argv[1], encoding="utf-8"):
        o = json.loads(line)
        if o.get("t") != "node" or o.get("kind") != "diag":
            continue
        if o.get("role") != "promoted_learning":
            continue
        api = o.get("api")
        if not api:
            continue
        for rid in request_by_label.get(api, []):
            emit({"t": "edge", "from": o["id"], "to": rid, "rel": "has_failure_mode",
                  "src": o.get("src") or "promoted_learning"})
