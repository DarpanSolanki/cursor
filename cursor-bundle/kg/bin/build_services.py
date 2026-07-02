#!/usr/bin/env python3
"""
build_services.py — service nodes + cross-service dependency edges for the KG.

Sources (all in-tree, cited as provenance — nothing guessed):
  - service list:        claude/workspace-state.md / services/ one-pagers
  - accounting outbound: exact <API> call counts parsed from accounting orchestration
  - dependency mapping:  claude/accounting/04-cross-module-deps.md (curated, evidence-based)

Emits JSONL nodes/edges on stdout.
"""
import json, sys

def emit(o): sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")

# 17 repos with a one-line role (role text mirrors services/ one-pagers + workspace-state).
SERVICES = {
 "novopay-platform-accounting-v2": "LMS core — loan accounts, GL posting, disbursement/repayment/foreclosure, EOD/BOD",
 "novopay-mfi-los": "Loan origination (LOS) — onboarding, group formation, credit underwriting; feeds accounting via Kafka",
 "novopay-platform-actor": "Identity/org — users, offices, roles, customers, actor accounts, use-cases",
 "novopay-platform-payments": "Payment rails (LCS) — NEFT/NACH/eNACH, collections, bank integration",
 "novopay-platform-batch": "Batch runner — schedules & drives EOD/BOD and accounting batch jobs",
 "novopay-platform-approval": "Maker-checker / approval workflow (submitApplication)",
 "novopay-platform-task": "BPMN / human-task orchestration (createOrUpdateTask, deleteTask)",
 "novopay-platform-notifications": "Notification templates & delivery (SMS/email/push)",
 "novopay-platform-dms": "Document management (verifyDocuments, storage)",
 "novopay-platform-masterdata-management": "Master data — product/scheme/config reference",
 "novopay-platform-audit": "Audit log (framework-level, implicit on every request)",
 "novopay-platform-authorization": "AuthZ — permissions/use-case checks",
 "novopay-platform-api-gateway": "Edge gateway — routing, auth, rate-limit",
 "novopay-platform-initial-setup": "Flyway migrations / tenant bootstrap",
 "novopay-platform-lib": "Shared platform-lib — orchestrator, navigation, cache, http-client, transaction model",
 "novopay-platform-webapp": "Angular web app (maker/checker UI)",
 "trustt-platform-reporting": "Reporting / RBI ADF / data extracts",
}
for repo, role in SERVICES.items():
    emit({"t":"node","id":f"service:{repo}","kind":"service","label":repo,
          "repo":repo,"role":role,"src":"claude/workspace-state.md"})

# Accounting OUTBOUND cross-service calls — exact API names + call counts from orchestration.
# (provenance: accounting deploy/application/orchestration/*.xml ; mapping: 04-cross-module-deps.md)
OUT = [
 ("novopay-platform-approval",      [("submitApplication",124)]),
 ("novopay-platform-notifications", [("getNotificationMessageByNotificationCode",101)]),
 ("novopay-platform-actor",         [("getUserDetails",56),("getUseCaseDetails",30),
                                     ("getOfficeDetails",17),("getCustomerDetails",2),
                                     ("createActorAccountDetails",2),("getRoleDetailsByUserId",1)]),
 ("novopay-platform-task",          [("deleteTask",10),("createOrUpdateTask",8)]),
 ("novopay-platform-dms",           [("verifyDocuments",1)]),
]
for target, apis in OUT:
    note = ", ".join(f"{n}×{c}" for n,c in apis)
    emit({"t":"edge","from":"service:novopay-platform-accounting-v2","to":f"service:{target}",
          "rel":"calls","note":note,
          "src":"novopay-platform-accounting-v2/deploy/application/orchestration/*_orc.xml"})

# Other curated cross-service edges (provenance: 04-cross-module-deps.md).
DOC = "claude/accounting/04-cross-module-deps.md"
CURATED = [
 # accounting also depends on (sync, internal API client):
 ("service:novopay-platform-accounting-v2","service:novopay-platform-masterdata-management","calls","product/scheme/config reference",DOC),
 ("service:novopay-platform-accounting-v2","service:novopay-platform-audit","emits","audit row per request (framework-level)",DOC),
 ("service:novopay-platform-accounting-v2","service:novopay-platform-lib","uses","orchestrator/navigation/cache/http-client/txn-model",DOC),
 # who calls INTO accounting:
 ("service:novopay-mfi-los","service:novopay-platform-accounting-v2","emits","loan-origination events (Kafka) → accounting consumes",DOC),
 ("service:novopay-platform-batch","service:novopay-platform-accounting-v2","triggers","EOD/BOD + accounting batch Requests",DOC),
 ("service:novopay-platform-payments","service:novopay-platform-accounting-v2","calls","repayment/collection (LCS) → accounting",DOC),
 ("service:novopay-platform-webapp","service:novopay-platform-accounting-v2","calls","maker/checker UI via api-gateway",DOC),
]
for frm,to,rel,note,src in CURATED:
    emit({"t":"edge","from":frm,"to":to,"rel":rel,"note":note,"src":src})

# Bridge the flow layer to the service layer: api:<name> -resolves_to-> service:<repo>.
# This lets `path`/`impact` traverse request -calls_api-> api -resolves_to-> service,
# answering "which requests hit actor?". Mapping per 04-cross-module-deps.md + API evidence.
API_TO_SERVICE = {
 "submitApplication":"novopay-platform-approval",
 "getNotificationMessageByNotificationCode":"novopay-platform-notifications",
 "getUserDetails":"novopay-platform-actor","getUseCaseDetails":"novopay-platform-actor",
 "getOfficeDetails":"novopay-platform-actor","getCustomerDetails":"novopay-platform-actor",
 "createActorAccountDetails":"novopay-platform-actor","getRoleDetailsByUserId":"novopay-platform-actor",
 "createOrUpdateTask":"novopay-platform-task","deleteTask":"novopay-platform-task",
 "verifyDocuments":"novopay-platform-dms",
 # accounting's own APIs invoked via orchestration (self-calls):
 "postTransaction":"novopay-platform-accounting-v2","getLoanAccountDetails":"novopay-platform-accounting-v2",
 "createOrUpdateLoanAccount":"novopay-platform-accounting-v2","getLoanProductDetails":"novopay-platform-accounting-v2",
 "loanAccountCollection":"novopay-platform-accounting-v2",
}
for api,svc in API_TO_SERVICE.items():
    emit({"t":"edge","from":f"api:{api}","to":f"service:{svc}","rel":"resolves_to",
          "note":"API target","src":"claude/accounting/04-cross-module-deps.md"})
