#!/usr/bin/env python3
"""Map every loan transaction as it actually is, and store it.

These flows work in production. The job is not to change them or to make them pass a harness —
it is to know them: what a caller must send, what comes back, which processors run in what
order, which other services get called, which error codes can come out, and which tables move.

Each fact is read from the artefact that owns it, never inferred:

  request / response shape   JTF templates the service ships
  mandatory + allowed values orchestration `<Validators>`
  processor order            orchestration `<Processors>`, `<Control>` branches marked
  internal + cross-service   `chains.jsonl` (derived from the same orchestration)
  error codes                the KG error index
  tables written             the KG CRUD edges

Rediscovering this per incident is what makes a two-line question cost an afternoon. Storing it
means the next session reads the map instead of re-deriving it.

    transaction_map.py                 map every loan transaction, write the artefact
    transaction_map.py --api NAME      one transaction, full detail
    transaction_map.py --markdown      human-readable reference
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
OUT = FLOW / "transaction_map.jsonl"
DOC = ROOT / ".cursor" / "loan-transaction-map.md"
KG = ROOT / "cursor-bundle" / "kg" / "bin" / "kg.py"

sys.path.insert(0, str(ROOT / "scripts" / "testing"))
sys.path.insert(0, str(ROOT / "cursor-bundle" / "kg" / "bin"))

import read_inquiry_worklist as w  # noqa: E402

# The money-moving and state-changing loan transactions. Read APIs are mapped by
# `read_inquiry_worklist.py`; this file is about the ones that write.
TRANSACTIONS = [
    "disburseLoan", "childLoanDisbursement", "loanDisbursementCancellation",
    "childLoanDisbursementCancellation", "loanRepayment", "childLoanRepayment",
    "loanPrepayment", "loanPartPrepayment", "loanForeclosure", "childLoanForeclosure",
    "loanDeathForeclosure", "loanWriteoff", "loanAccountReopening", "childLoanReopening",
    "loanAccountReschedule", "loanAccountRestructuring", "childLoanRestructuring",
    "transactionReversal", "childLoanTransactionReversal", "waiveLoanAccountCharges",
    "childWaiveLoanAccountCharges", "loanAccountExcessAmountRefund",
    "proactiveExcessAmountRefund", "loanAccountClosure", "postTransaction",
    "reverseTransaction", "loanRecurringPaymentBatchApi", "loanAdvanceRepayment",
]

CONTROL_FIELDS = ("function_code", "function_sub_code", "run_mode")

_CONTROL = re.compile(r'<Control[^>]*pattern="([^"]*)"[^>]*value="([^"]*)"', re.I)

ACCOUNTING = "trustt-platform-accounting"

REPO_TRANSACTIONS: dict[str, list[str]] = {
    "trustt-platform-actor": [
        "createMfiCustomer", "createOrUpdateCustomer", "createMinimumCustomer",
        "createEkycCustomer", "backfillCustomerKycDetails", "blockOrUnblockCustomer",
        "createCustomerAtBank", "createBankLead", "createOrUpdateAgent",
        "createOrUpdateAgentEmployee", "createOrUpdateEmployee", "createOrUpdateDevice",
        "allocateCollections", "createOrUpdateCollection",
    ],
    "trustt-platform-los": [
        "triggerDisburseLoan", "submitDisbursementAccountDetails", "disburseLoanCallBack",
        "createBorrower", "createOrUpdateLoanApp", "createOrUpdateGroup", "createEStamp",
        "createOrUpdateBorrowerKycDetails", "createOrUpdateBorrowerDetails",
        "createOrUpdateFinancialDetails", "createOrUpdateCreditBureauReport",
        "processLoanAppIdForDisbursementAfterPDC",
    ],
    "trustt-platform-payments": [
        "createOrUpdateBulkCollection", "doMfiCollections", "doCollections",
        "collectionLoanRepayment", "autoAllocateCollections", "primaryAllocateCollection",
        "createCollection", "createCollectionAttempt", "cancelCollections",
        "cancelCollectionForeClosure", "collectAmountAfterRectification",
        "markCollectionsAsSettled",
    ],
    "trustt-platform-task": [
        "approveTaskForCollection", "bulkCreateTask", "bulkUpdateTaskStatus",
        "calculateUserTatBatch", "createOrUpdateMfiTaskByCode", "createOrUpdateTask",
        "createOrUpdateTaskMfi", "createTaskBatch", "createTaskDelegation",
        "createTaskWorkflow", "deleteTask", "deleteTaskMfi", "deleteTaskType",
        "executeTaskPortfolioTransfer", "notifyUsersForPendingTasksJob",
        "rejectExpiredBatchJob", "rejectTaskForCollection", "reopenClosedTask",
        "rollbackTaskPortfolioTransfer", "sendMeetingCenterPendingNoti",
        "updateAooTaskDetailsNewApprover", "updateDataCurrentTaskAndCreateNewTask",
        "updateTaskDelegation", "updateTaskStatus", "updateTaskStatusAndCallApi",
        "updateTaskStatusForTaskIds", "updateTaskWorkflow",
        "validateCashLimitIncreaseTaskForSo",
    ],
    "trustt-platform-approval": [
        "approveApplication", "checkIfApplicationIsPending", "createOrUpdateDraftApplication",
        "deleteDraftApplication", "rejectApplication", "sendApplicationForClarification",
        "submitApplication", "updateAooApplicationDetailsNewApprover", "updateApplication",
        "updateApprover", "updateAssigneeByTaskId",
    ],
}


def orchestration_sites(repo: str) -> dict[str, tuple[str, int, str]]:
    """Same windowing as `read_inquiry_worklist.request_sites()`, repo-parametrized.

    `_contract_scan.orchestration_xmls()` already globs `**/*_orc.xml` OR
    `**/orchestration/**/*.xml` filtered on `<Request name=` — that fallback is why this
    works unmodified on los/payments/task/approval, none of which use the `_orc.xml` suffix
    accounting does (`ServiceOrchestrationXML.xml`, `orc_mfi.xml`, `mfi_orchestration.xml`).
    """
    from _contract_scan import orchestration_xmls
    sites: dict[str, tuple[str, int, str]] = {}
    for raw in orchestration_xmls(str(ROOT / repo)):
        path = pathlib.Path(raw)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(w._REQUEST.finditer(text))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            line = text.count("\n", 0, m.start()) + 1
            sites.setdefault(m.group(1), (str(path.relative_to(ROOT)), line, text[m.start():end]))
    return sites


def template_index_fuzzy(repo: str, kind: str) -> dict[str, pathlib.Path]:
    """`read_inquiry_worklist._template_index()` requires the literal `_requestTemplate.json`
    / `_responseTemplate.json` suffix, which accounting spells consistently everywhere. actor,
    los and payments do not: `_requesstTemplate.json`, `_requesteTemplate.json`,
    `_requestTemple.json`, `_requestTeamplate.json`, `_requestTemplete.json`,
    `_requestTemplare.json`, `_request.json`, `_requsetTemplate.json` all ship there too, and
    every one of them was a strict-suffix miss — the same failure mode as assuming the batch
    scanner's shape everywhere. No JTF filename in any repo carries more than one underscore
    (checked across all six repos), so splitting on the first `_` recovers the api name
    regardless of how the rest of the filename is spelled.
    """
    root = ROOT / repo / "deploy" / "application" / "templates" / kind
    if not root.is_dir():
        return {}
    out: dict[str, pathlib.Path] = {}
    for p in sorted(root.rglob("*.json")):
        stem = p.stem
        if "_" not in stem:
            continue
        out.setdefault(stem.split("_", 1)[0], p)
    return out


def chains_for_repo(repo: str) -> dict[str, dict]:
    path = FLOW / "chains.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row = json.loads(line)
            if row.get("repo") == repo:
                out.setdefault(row["request"], row)
    return out


def kg(*args: str) -> str:
    try:
        r = subprocess.run([sys.executable, str(KG), *args], cwd=str(ROOT),
                           capture_output=True, text=True, timeout=120)
        return r.stdout
    except (subprocess.TimeoutExpired, OSError):
        return ""


def chains() -> dict[str, dict]:
    path = FLOW / "chains.jsonl"
    if not path.is_file():
        return {}
    out: dict[str, dict] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.startswith("#"):
            row = json.loads(line)
            out.setdefault(row["request"], row)
    return out


_CRUD = re.compile(r"^\s+([RWD])\s+(\w+)\s", re.M)


def db_footprint(api: str, repo: str = ACCOUNTING) -> tuple[list[str], list[str]]:
    """Tables this flow writes and reads, from the KG CRUD edges.

    `kg crud` prints `      W loan_account   upsert` — one letter, not the word WRITE.
    Matching on WRITE/INSERT/UPDATE returned nothing for all 24 transactions, and an
    always-empty field reads as "this flow touches no tables".
    """
    arg = api if repo == ACCOUNTING else f"{repo}/{api}"
    out = kg("crud", arg)
    writes = sorted({m.group(2) for m in _CRUD.finditer(out) if m.group(1) in ("W", "D")})
    reads = sorted({m.group(2) for m in _CRUD.finditer(out) if m.group(1) == "R"})
    return writes, reads


def error_codes(api: str, block: str, repo: str = ACCOUNTING) -> list[str]:
    """Every code this flow can raise: its own validators, plus what its processors throw.

    The orchestration declares only the codes its `<IParam>` validators use. Thirteen of the
    24 transactions declared none — not because they cannot fail, but because they validate
    inside a processor. `loanPrepayment` has 21 codes the orchestration never mentions.
    """
    declared = set(re.findall(r'errorCode="([A-Za-z]{2,8}-\d+|\d+)"', block))
    return sorted(declared | thrown(api, repo))


def thrown(api: str, repo: str = ACCOUNTING) -> set[str]:
    import sqlite3
    db = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
    if not db.is_file():
        return set()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    rid = f"request:{repo}/{api}"
    rows = con.execute(
        """SELECT DISTINCT n.label FROM edges e1
           JOIN edges e2 ON e2.src_id = e1.dst_id
           JOIN nodes n ON n.id = e2.dst_id
           WHERE e1.src_id = ? AND e1.rel='invokes' AND e2.rel='throws' AND n.kind='error'""",
        (rid,)).fetchall()
    con.close()
    return {r[0] for r in rows}


def controls(block: str) -> list[str]:
    return [f"{p} = {v}" for p, v in _CONTROL.findall(block)][:12]


def map_one(api: str, sites: dict, req_idx: dict, resp_idx: dict,
            chain_idx: dict, repo: str = ACCOUNTING) -> dict:
    site = sites.get(api)
    block = site[2] if site else ""
    required, allowed = w.validator_contract(block) if block else ([], {})
    chain = chain_idx.get(api) or {}
    writes, reads = db_footprint(api, repo)

    request_fields = w.contract_from_template(req_idx.get(api), api)
    response_fields = w.contract_from_template(resp_idx.get(api), api)

    return {
        "api": api,
        "repo": repo,
        "orchestration": f"{site[0]}:{site[1]}" if site else None,
        "request_template": str(req_idx[api].relative_to(ROOT)) if api in req_idx else None,
        "response_template": str(resp_idx[api].relative_to(ROOT)) if api in resp_idx else None,
        "headers": {k: allowed[k] for k in CONTROL_FIELDS if k in allowed},
        "mandatory_fields": required,
        "allowed_values": {k: v for k, v in allowed.items() if k not in CONTROL_FIELDS},
        "request_fields": [f["path"] for f in request_fields],
        "response_fields": [f["path"] for f in response_fields],
        "processors": w._PROCESSOR.findall(block) if block else [],
        "control_branches": controls(block),
        "internal_apis": chain.get("internal_apis") or [],
        "cross_service_apis": chain.get("cross_service_apis") or [],
        "tables_written": writes,
        "tables_read": reads,
        "error_codes": error_codes(api, block),
    }


def build(only: str | None = None, repo: str = ACCOUNTING) -> list[dict]:
    if repo == ACCOUNTING:
        sites = w.request_sites()
        req_idx, resp_idx = w._template_index("request"), w._template_index("response")
        chain_idx = chains()
        names = [only] if only else TRANSACTIONS
    else:
        sites = orchestration_sites(repo)
        req_idx = template_index_fuzzy(repo, "request")
        resp_idx = template_index_fuzzy(repo, "response")
        chain_idx = chains_for_repo(repo)
        names = [only] if only else REPO_TRANSACTIONS.get(repo, [])
    rows = []
    for api in names:
        row = map_one(api, sites, req_idx, resp_idx, chain_idx, repo=repo)
        if row["orchestration"] or row["request_template"]:
            rows.append(row)
    return rows


def markdown(rows: list[dict]) -> str:
    out = ["# Loan transaction map (generated — do not hand-edit)",
           "",
           "`python3 scripts/testing/transaction_map.py` regenerates this from the orchestration,",
           "the shipped JTF templates and the KG. These flows run in production; this is what they",
           "are, not what they should be.",
           "",
           "**Control fields are headers**, never body: `function_code`, `function_sub_code`,",
           "`run_mode`. Sent in the body the gateway answers `11008 Invalid run_mode`.",
           ""]
    for r in rows:
        out.append(f"## {r['api']}")
        out.append("")
        if r["orchestration"]:
            out.append(f"- **Orchestration:** `{r['orchestration']}`")
        if r["request_template"]:
            out.append(f"- **Request template:** `{r['request_template']}`")
        if r["headers"]:
            hdr = ", ".join(f"`{k}={v}`" for k, v in r["headers"].items())
            out.append(f"- **Headers:** {hdr}")
        if r["mandatory_fields"]:
            out.append(f"- **Mandatory:** {', '.join('`'+f+'`' for f in r['mandatory_fields'])}")
        if r["cross_service_apis"]:
            out.append(f"- **Calls other services:** "
                       f"{', '.join('`'+a+'`' for a in r['cross_service_apis'])}")
        if r["internal_apis"]:
            out.append(f"- **Internal APIs:** "
                       f"{', '.join('`'+a+'`' for a in dict.fromkeys(r['internal_apis']))}")
        if r["tables_written"]:
            more = f" (+{len(r['tables_written'])-12} more)" if len(r["tables_written"]) > 12 else ""
            out.append(f"- **Writes:** "
                       f"{', '.join('`'+t+'`' for t in r['tables_written'][:12])}{more}")
        if r["error_codes"]:
            out.append(f"- **Error codes:** {', '.join(r['error_codes'][:12])}")
        if r["processors"]:
            out.append(f"- **Processors ({len(r['processors'])}):** "
                       f"{', '.join('`'+p+'`' for p in r['processors'][:10])}"
                       + (" …" if len(r["processors"]) > 10 else ""))
        if r["control_branches"]:
            out.append(f"- **Branches:** {'; '.join(r['control_branches'][:6])}")
        out.append("")
    return "\n".join(out) + "\n"


def _resolve_repo(name: str | None) -> str:
    if not name:
        return ACCOUNTING
    return name if name.startswith("trustt-platform-") else f"trustt-platform-{name}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--api")
    ap.add_argument("--repo", help="e.g. actor, los, payments, task, approval "
                                   "(default: accounting)")
    ap.add_argument("--write", action="store_true",
                     help="with --repo, persist to a repo-suffixed jsonl/md pair "
                          "instead of the default accounting artefact")
    ap.add_argument("--markdown", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    repo = _resolve_repo(args.repo)

    if repo != ACCOUNTING:
        rows = build(args.api, repo=repo)
        if not args.write:
            print(json.dumps(rows, indent=1))
            return 0
        suffix = repo.replace("trustt-platform-", "")
        out = FLOW / f"transaction_map.{suffix}.jsonl"
        doc = ROOT / ".cursor" / f"loan-transaction-map.{suffix}.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            fh.write(f"# {repo} write-transaction map — orchestration + JTF templates + KG. "
                      f"Generated.\n")
            for r in rows:
                fh.write(json.dumps(r) + "\n")
        doc.write_text(markdown(rows), encoding="utf-8")
        templated = [r for r in rows if r["request_template"]]
        with_codes = [r for r in rows if r["error_codes"]]
        print(f"{repo}: {len(rows)} transaction(s)")
        print(f"  {len(templated):3} with a JTF request contract")
        print(f"  {len(with_codes):3} with at least one error code")
        print(f"  → {out.relative_to(ROOT)}")
        print(f"  → {doc.relative_to(ROOT)}")
        return 0

    rows = build(args.api)

    if args.api or args.json:
        print(json.dumps(rows, indent=1))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# Loan transaction map — orchestration + JTF templates + KG. Generated.\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    doc = markdown(rows)
    if args.markdown:
        print(doc)
    else:
        DOC.write_text(doc, encoding="utf-8")

    cross = [r for r in rows if r["cross_service_apis"]]
    templated = [r for r in rows if r["request_template"]]
    print(f"transaction map: {len(rows)} loan transaction(s)")
    print(f"  {len(templated):3} with a JTF request contract")
    print(f"  {len(cross):3} that call another service")
    print(f"  → {OUT.relative_to(ROOT)}")
    print(f"  → {DOC.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
