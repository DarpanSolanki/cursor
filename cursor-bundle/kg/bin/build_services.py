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
 "trustt-platform-accounting": "LMS core — loan accounts, GL posting, disbursement/repayment/foreclosure, EOD/BOD",
 "trustt-platform-los": "Loan origination (LOS) — onboarding, group formation, credit underwriting; feeds accounting via Kafka",
 "trustt-platform-actor": "Identity/org — users, offices, roles, customers, actor accounts, use-cases",
 "trustt-platform-payments": "Payment rails (LCS) — NEFT/NACH/eNACH, collections, bank integration",
 "trustt-platform-batch": "Batch runner — schedules & drives EOD/BOD and accounting batch jobs",
 "trustt-platform-approval": "Maker-checker / approval workflow (submitApplication)",
 "trustt-platform-task": "BPMN / human-task orchestration (createOrUpdateTask, deleteTask)",
 "trustt-platform-notifications": "Notification templates & delivery (SMS/email/push)",
 "trustt-platform-dms": "Document management (verifyDocuments, storage)",
 "trustt-platform-masterdata-management": "Master data — product/scheme/config reference",
 "trustt-platform-audit": "Audit log (framework-level, implicit on every request)",
 "trustt-platform-authorization": "AuthZ — permissions/use-case checks",
 "trustt-platform-api-gateway": "Edge gateway — routing, auth, rate-limit",
 "trustt-platform-initial-setup": "Flyway migrations / tenant bootstrap",
 "trustt-platform-lib": "Shared platform-lib — orchestrator, navigation, cache, http-client, transaction model",
 "trustt-platform-webapp": "Angular web app (maker/checker UI)",
 "trustt-platform-reporting": "Reporting / RBI ADF / data extracts",
}
for repo, role in SERVICES.items():
    emit({"t":"node","id":f"service:{repo}","kind":"service","label":repo,
          "repo":repo,"role":role,"src":"claude/workspace-state.md"})

# Accounting OUTBOUND cross-service calls — exact API names + call counts from orchestration.
# (provenance: accounting deploy/application/orchestration/*.xml ; mapping: 04-cross-module-deps.md)
OUT = [
 ("trustt-platform-approval",      [("submitApplication",124)]),
 ("trustt-platform-notifications", [("getNotificationMessageByNotificationCode",101)]),
 ("trustt-platform-actor",         [("getUserDetails",56),("getUseCaseDetails",30),
                                     ("getOfficeDetails",17),("getCustomerDetails",2),
                                     ("createActorAccountDetails",2),("getRoleDetailsByUserId",1)]),
 ("trustt-platform-task",          [("deleteTask",10),("createOrUpdateTask",8)]),
 ("trustt-platform-dms",           [("verifyDocuments",1)]),
]
for target, apis in OUT:
    note = ", ".join(f"{n}×{c}" for n,c in apis)
    emit({"t":"edge","from":"service:trustt-platform-accounting","to":f"service:{target}",
          "rel":"calls","note":note,
          "src":"trustt-platform-accounting/deploy/application/orchestration/*_orc.xml"})

# Other curated cross-service edges (provenance: 04-cross-module-deps.md).
DOC = "claude/accounting/04-cross-module-deps.md"
CURATED = [
 # accounting also depends on (sync, internal API client):
 ("service:trustt-platform-accounting","service:trustt-platform-masterdata-management","calls","product/scheme/config reference",DOC),
 ("service:trustt-platform-accounting","service:trustt-platform-audit","emits","audit row per request (framework-level)",DOC),
 ("service:trustt-platform-accounting","service:trustt-platform-lib","uses","orchestrator/navigation/cache/http-client/txn-model",DOC),
 # who calls INTO accounting:
 ("service:trustt-platform-los","service:trustt-platform-accounting","emits","loan-origination events (Kafka) → accounting consumes",DOC),
 ("service:trustt-platform-batch","service:trustt-platform-accounting","triggers","EOD/BOD + accounting batch Requests",DOC),
 ("service:trustt-platform-payments","service:trustt-platform-accounting","calls","repayment/collection (LCS) → accounting",DOC),
 ("service:trustt-platform-webapp","service:trustt-platform-accounting","calls","maker/checker UI via api-gateway",DOC),
]
for frm,to,rel,note,src in CURATED:
    emit({"t":"edge","from":frm,"to":to,"rel":rel,"note":note,"src":src})

# Bridge the flow layer to the service layer: api:<name> -resolves_to-> service:<repo>.
# This lets `path`/`impact` traverse request -calls_api-> api -resolves_to-> service,
# answering "which requests hit actor?". Mapping per 04-cross-module-deps.md + API evidence.
API_TO_SERVICE = {
 "submitApplication":"trustt-platform-approval",
 "getNotificationMessageByNotificationCode":"trustt-platform-notifications",
 "getUserDetails":"trustt-platform-actor","getUseCaseDetails":"trustt-platform-actor",
 "getOfficeDetails":"trustt-platform-actor","getCustomerDetails":"trustt-platform-actor",
 "createActorAccountDetails":"trustt-platform-actor","getRoleDetailsByUserId":"trustt-platform-actor",
 "createOrUpdateTask":"trustt-platform-task","deleteTask":"trustt-platform-task",
 "verifyDocuments":"trustt-platform-dms",
 # accounting's own APIs invoked via orchestration (self-calls):
 "postTransaction":"trustt-platform-accounting","getLoanAccountDetails":"trustt-platform-accounting",
 "createOrUpdateLoanAccount":"trustt-platform-accounting","getLoanProductDetails":"trustt-platform-accounting",
 "loanAccountCollection":"trustt-platform-accounting",
}
for api,svc in API_TO_SERVICE.items():
    emit({"t":"edge","from":f"api:{api}","to":f"service:{svc}","rel":"resolves_to",
          "note":"API target","src":"claude/accounting/04-cross-module-deps.md"})
