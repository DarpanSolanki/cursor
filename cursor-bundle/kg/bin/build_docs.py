#!/usr/bin/env python3
"""
build_docs.py — fold every knowledge file into the ONE core graph.

Each claude/**/*.md becomes a `doc` node, and is AUTO-LINKED to the requests /
services it names (`mentions` edges) so the graph is the single entry point over
hundreds of files — no orphan docs. Plus a few curated `documents` / `next` edges
(DPIC pipeline) that can't be inferred from text alone.

Reads the request/service ids already emitted by the other builders (passed as the
node-id file) so links only point at real nodes. stdout = JSONL.

Usage: build_docs.py <existing-nodes.jsonl>
"""
import os, re, json, sys, glob

ROOT = "/home/darpan/darpan"
DOCROOT = os.path.join(ROOT, "claude")

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

# Load ids already in the graph so `mentions` only links to real nodes.
request_ids, service_repos = set(), {}
if len(sys.argv) > 1:
    for line in open(sys.argv[1], encoding="utf-8"):
        o = json.loads(line)
        if o.get("t") != "node": continue
        if o["kind"] == "request": request_ids.add(o["label"])
        elif o["kind"] == "service": service_repos[o["label"]] = o["id"]

# request names are distinctive camelCase tokens; match on word boundaries.
req_re = {name: re.compile(r"\b" + re.escape(name) + r"\b") for name in request_ids if len(name) >= 6}

def title_of(path):
    for line in open(path, encoding="utf-8", errors="replace"):
        if line.startswith("# "): return line[2:].strip()
    return os.path.basename(path)

docs = sorted(glob.glob(os.path.join(DOCROOT, "**", "*.md"), recursive=True))
for path in docs:
    rel = os.path.relpath(path, ROOT)
    if "/kg/" in path and "/data/" in path:  # skip generated
        continue
    did = "doc:" + os.path.relpath(path, DOCROOT)
    emit({"t":"node","id":did,"kind":"doc","label":title_of(path),"src":rel})
    text = open(path, encoding="utf-8", errors="replace").read()
    seen=set()
    for name, rx in req_re.items():
        if name in text and rx.search(text):
            seen.add(name)
            emit({"t":"edge","from":did,"to":f"request:{name}","rel":"mentions","src":rel})
    for repo, sid in service_repos.items():
        if repo in text:
            emit({"t":"edge","from":did,"to":sid,"rel":"mentions","src":rel})

# Curated edges that text can't express ------------------------------------
DPIC = "claude/dpic/04-dpic-flow.md"
# DPIC daily/EMI pipeline order (3 separate scheduled jobs, not an orchestration chain):
emit({"t":"edge","from":"request:dpiAccrualCalculation","to":"request:dpiAccrualBooking","rel":"next","src":DPIC})
emit({"t":"edge","from":"request:dpiAccrualBooking","to":"request:dpiBilling","rel":"next","src":DPIC})
# the flow doc documents the three requests explicitly:
for r in ("dpiAccrualCalculation","dpiAccrualBooking","dpiBilling"):
    emit({"t":"edge","from":"doc:dpic/04-dpic-flow.md","to":f"request:{r}","rel":"documents","src":DPIC})

# Authoritative doc per principal loan transaction (curated — the canonical "read this first").
AUTHORITATIVE = {
 "engines/disbursement-engine.md": ["disburseLoan","childLoanDisbursement","loanDisbursementCancellation",
                                    "childLoanDisbursementCancellation"],
 "engines/repayment-engine.md":    ["loanRepayment","childLoanRepayment","advanceRepayment"],
 "engines/posting-engine.md":      ["postTransaction"],
 "flows/foreclosure-and-closure.md":["loanForeclosure","childLoanForeclosure","individualChildLoanForeclosure",
                                     "loanDeathForeclosure","cancelLoanForeclosure","loanWriteoff"],
 "accounting/07-loan-account-lifecycle.md": ["loanAccountRestructuring","childLoanRestructuring",
                                     "loanAccountReopening","childLoanReopening","loanAccountRebooking",
                                     "childLoanRebooking","loanPrepayment","loanAccountPartPrepayment",
                                     "childLoanPartPrepayment","loanAccountExcessAmountRefund"],
 "accounting/05-flows.md":         ["loanAccountTransactionReversal","childLoanTransactionReversal",
                                     "generateRepaymentSchedule"],
 "accounting/worked-examples/death-foreclosure-walkthrough.md": ["loanDeathForeclosure"],
}
import os as _os
for doc, reqs in AUTHORITATIVE.items():
    if not _os.path.exists(_os.path.join(DOCROOT, doc)): continue
    did = "doc:" + doc
    for r in reqs:
        if r in request_ids:
            emit({"t":"edge","from":did,"to":f"request:{r}","rel":"documents","src":"claude/"+doc})
