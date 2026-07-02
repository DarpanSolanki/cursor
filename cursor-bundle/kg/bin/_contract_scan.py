#!/usr/bin/env python3
"""Shared orchestration + Kafka contract scanner (stdlib only)."""

from __future__ import annotations

import glob
import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

REQ_RE = re.compile(r'<Request\s+[^>]*name="([^"]+)"')
PROC_RE = re.compile(r'<Processor\s+[^>]*bean="([^"]+)"')
API_RE = re.compile(r'<API\s+([^>]*)/?>')
ATTR_RE = re.compile(r'(\w+)="([^"]*)"')
CTRL_RE = re.compile(r'<Control\b[^>]*>')
CTRL_FC = re.compile(r'pattern="\$\{function_code\}"[^>]*value="([^"]+)"')
CTRL_FSC = re.compile(r'pattern="\$\{function_sub_code\}"[^>]*value="([^"]+)"')
CTRL_CLOSE = re.compile(r'</Control>')
REQ_CLOSE = re.compile(r'</Request>')

TOPIC_RE = re.compile(r'<topicPrefix>([^<]+)</topicPrefix>')
BEAN_RE = re.compile(r'<bean>([^<]+)</bean>')
PRODUCER_ID_RE = re.compile(r'<producerId>([^<]+)</producerId>')

ID_PREFIX_TO_SERVICE: dict[str, str] = {
    "accounting": "novopay-platform-accounting-v2",
    "payments": "novopay-platform-payments",
    "los": "novopay-mfi-los",
    "actor": "novopay-platform-actor",
    "task": "novopay-platform-task",
    "approval": "novopay-platform-approval",
    "notification": "novopay-platform-notifications",
    "notifications": "novopay-platform-notifications",
    "dms": "novopay-platform-dms",
    "masterdata": "novopay-platform-masterdata-management",
    "batch": "novopay-platform-batch",
    "authorization": "novopay-platform-authorization",
    "audit": "novopay-platform-audit",
}

MONEY_KEYWORDS = (
    "disburse", "repay", "prepay", "foreclos", "collection", "transaction", "posting",
    "accrual", "billing", "dpi", "dpd", "gl", "zerois", "cancel", "reversal", "writeoff",
    "writeoff", "mandate", "neft", "mft", "ledger", "payment", "refund", "excess",
)

# Curated Kafka consumer → orchestration request (code-verified entry points)
KAFKA_CONSUMER_REQUEST: dict[str, tuple[str, str]] = {
    "lmsMessageBrokerConsumer": ("novopay-platform-accounting-v2", "disburseLoan"),
    "bulkCollectionFailedRecordConsumer": ("novopay-platform-accounting-v2", "bulkCollectionFailedRecord"),
}

KAFKA_TOPIC_REQUEST: dict[str, tuple[str, str]] = {
    "disburse_loan_api_": ("novopay-mfi-los", "disburseLoan"),
    "los_lms_disbursement_sync": ("novopay-platform-accounting-v2", "disburseLoan"),
    "bulk_collection_data_": ("novopay-platform-accounting-v2", "bulkCollectionData"),
    "bulk_collection_data_failed_": ("novopay-platform-accounting-v2", "bulkCollectionFailedRecord"),
}

# HTTP calls known from Java (not always in orchestration XML)
CURATED_HTTP_CONTRACTS: list[dict] = [
    {
        "id": "contract:http:payments:batchExpiry->accounting:updateCollectionBatchDetails",
        "producer_service": "novopay-platform-payments",
        "producer_request": "updateExpiredScheduledBatchStatus",
        "consumer_service": "novopay-platform-accounting-v2",
        "consumer_request": "updateCollectionBatchDetails",
        "function_sub_code": "EXPIRED",
        "money": True,
        "precedents": ["SDCP-10400"],
        "src": "MfiCollectionsDAOService.updateBatchExpirationToLMS",
    },
]


def repo_name(path: str) -> str:
    parts = os.path.abspath(path).split(os.sep)
    for seg in parts:
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return os.path.basename(path.rstrip(os.sep))


def orchestration_xmls(repo_dir: str) -> list[str]:
    cands = set(glob.glob(os.path.join(repo_dir, "**", "*_orc.xml"), recursive=True))
    cands |= set(glob.glob(os.path.join(repo_dir, "**", "orchestration", "**", "*.xml"), recursive=True))
    out = []
    for f in cands:
        try:
            with open(f, encoding="utf-8", errors="replace") as fh:
                head = fh.read(200_000)
            if "<Request name=" in head:
                out.append(f)
        except OSError:
            pass
    return sorted(out)


def message_broker_xmls(repo_dir: str) -> list[str]:
    return sorted(glob.glob(os.path.join(repo_dir, "**", "MessageBroker.xml"), recursive=True))


def is_money(*parts: str) -> bool:
    blob = " ".join(p for p in parts if p).lower()
    return any(k in blob for k in MONEY_KEYWORDS)


def infer_service_from_api_id(api_id: str) -> str | None:
    if not api_id:
        return None
    low = api_id.lower()
    for prefix, svc in ID_PREFIX_TO_SERVICE.items():
        if low.startswith(prefix + "_") or low.startswith(prefix):
            return svc
    return None


@dataclass
class ApiCall:
    api_name: str
    api_id: str
    producer_repo: str
    producer_request: str
    function_code: str | None
    function_sub_code: str | None
    src: str


@dataclass
class ScanResult:
    request_owners: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    requests_by_repo: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    api_calls: list[ApiCall] = field(default_factory=list)
    kafka_consumers: list[dict] = field(default_factory=list)
    kafka_producers: list[dict] = field(default_factory=list)
    http_contracts: list[dict] = field(default_factory=list)
    kafka_contracts: list[dict] = field(default_factory=list)


def scan_repo(repo_dir: str, result: ScanResult) -> None:
    repo = repo_name(repo_dir)
    for path in orchestration_xmls(repo_dir):
        rel = os.path.relpath(path, start=os.getcwd())
        cur_req: str | None = None
        ctrl_stack: list[tuple[str | None, str | None]] = []
        with open(path, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                m = REQ_RE.search(line)
                if m:
                    cur_req = m.group(1)
                    result.request_owners[cur_req].add(repo)
                    result.requests_by_repo[repo].add(cur_req)
                    ctrl_stack = []
                    continue
                if cur_req is None:
                    continue
                for cm in CTRL_RE.finditer(line):
                    tag = cm.group(0)
                    fc = CTRL_FC.search(tag)
                    fsc = CTRL_FSC.search(tag)
                    ctrl_stack.append((
                        fc.group(1) if fc else None,
                        fsc.group(1) if fsc else None,
                    ))
                for _ in CTRL_CLOSE.finditer(line):
                    if ctrl_stack:
                        ctrl_stack.pop()
                am = API_RE.search(line)
                if am:
                    attrs = dict(ATTR_RE.findall(am.group(1)))
                    name = attrs.get("name") or attrs.get("uri") or "api"
                    api_id = attrs.get("id") or ""
                    fc = next((c[0] for c in reversed(ctrl_stack) if c[0]), None)
                    fsc = next((c[1] for c in reversed(ctrl_stack) if c[1]), None)
                    result.api_calls.append(ApiCall(
                        api_name=name,
                        api_id=api_id,
                        producer_repo=repo,
                        producer_request=cur_req,
                        function_code=fc,
                        function_sub_code=fsc,
                        src=f"{rel}:{lineno}",
                    ))
                if REQ_CLOSE.search(line):
                    cur_req = None

    for path in message_broker_xmls(repo_dir):
        rel = os.path.relpath(path, start=os.getcwd())
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for topic_m, bean_m in zip(TOPIC_RE.finditer(text), BEAN_RE.finditer(text)):
            result.kafka_consumers.append({
                "repo": repo,
                "topic_prefix": topic_m.group(1).strip(),
                "bean": bean_m.group(1).strip(),
                "src": rel,
            })
        for pid in PRODUCER_ID_RE.finditer(text):
            result.kafka_producers.append({
                "repo": repo,
                "producer_id": pid.group(1).strip(),
                "src": rel,
            })


def resolve_api_owner(api_name: str, api_id: str, owners: dict[str, set[str]]) -> str | None:
    if api_name in owners and len(owners[api_name]) == 1:
        return next(iter(owners[api_name]))
    svc = infer_service_from_api_id(api_id)
    if svc:
        return svc
    if api_name in owners:
        return sorted(owners[api_name])[0]
    return None


def build_http_contracts(result: ScanResult) -> list[dict]:
    contracts: list[dict] = []
    seen: set[str] = set()

    for call in result.api_calls:
        callee_svc = resolve_api_owner(call.api_name, call.api_id, result.request_owners)
        if not callee_svc or callee_svc == call.producer_repo:
            continue
        cid = f"contract:http:{call.producer_repo}:{call.producer_request}->{callee_svc}:{call.api_name}"
        if cid in seen:
            continue
        seen.add(cid)
        contracts.append({
            "id": cid,
            "protocol": "HTTP_INTERNAL",
            "producer": {
                "service": call.producer_repo,
                "request": call.producer_request,
            },
            "consumer": {
                "service": callee_svc,
                "request": call.api_name,
                "api": call.api_name,
            },
            "function_code": call.function_code,
            "function_sub_code": call.function_sub_code,
            "money": is_money(call.producer_request, call.api_name),
            "tests": {"ftg_id": None, "coverage": "gap"},
            "precedents": [],
            "src": call.src,
        })

    for row in CURATED_HTTP_CONTRACTS:
        cid = row["id"]
        if cid not in seen:
            seen.add(cid)
            contracts.append({
                "id": cid,
                "protocol": "HTTP_INTERNAL",
                "producer": {
                    "service": row["producer_service"],
                    "request": row["producer_request"],
                },
                "consumer": {
                    "service": row["consumer_service"],
                    "request": row["consumer_request"],
                    "api": row["consumer_request"],
                },
                "function_sub_code": row.get("function_sub_code"),
                "money": row.get("money", True),
                "tests": {"ftg_id": "ftf:foreclosure.batch_expiry_lms", "coverage": "partial"},
                "precedents": row.get("precedents", []),
                "src": row.get("src", "curated"),
            })
    return contracts


def build_kafka_contracts(result: ScanResult) -> list[dict]:
    contracts: list[dict] = []
    seen: set[str] = set()

    for cons in result.kafka_consumers:
        topic = cons["topic_prefix"]
        consumer_repo = cons["repo"]
        bean = cons["bean"]
        req: str | None = None
        producer_svc: str | None = None
        if bean in KAFKA_CONSUMER_REQUEST:
            _, req = KAFKA_CONSUMER_REQUEST[bean]
        if topic in KAFKA_TOPIC_REQUEST:
            producer_svc, topic_req = KAFKA_TOPIC_REQUEST[topic]
            req = req or topic_req
        cid = f"contract:kafka:{topic}->{consumer_repo}:{bean}"
        if cid in seen:
            continue
        seen.add(cid)
        contracts.append({
            "id": cid,
            "protocol": "KAFKA",
            "producer": {
                "service": producer_svc or "?",
                "topic_prefix": topic,
            },
            "consumer": {
                "service": consumer_repo,
                "bean": bean,
                "request": req,
            },
            "money": is_money(topic, bean, req or ""),
            "tests": {"ftg_id": None, "coverage": "gap"},
            "precedents": [],
            "src": cons["src"],
        })

    # disburse sync back to LOS
    sync_id = "contract:kafka:accounting:los_lms_disbursement_sync->los:DisbursementSync"
    if sync_id not in seen:
        contracts.append({
            "id": sync_id,
            "protocol": "KAFKA",
            "producer": {"service": "novopay-platform-accounting-v2", "topic_prefix": "los_lms_disbursement_sync"},
            "consumer": {"service": "novopay-mfi-los", "bean": "DisbursementSyncService", "request": "disburseLoan"},
            "money": True,
            "tests": {"ftg_id": "ftf:disburse.kafka", "coverage": "gap"},
            "precedents": ["GAP-entity_type"],
            "src": "LmsMessageBrokerConsumer + DisbursementSyncService",
        })
    return contracts


def scan_workspace(workspace: Path, repos: list[str] | None = None) -> ScanResult:
    result = ScanResult()
    if repos is None:
        repos = sorted(
            d.name for d in workspace.iterdir()
            if d.is_dir() and (d.name.startswith("novopay-") or d.name.startswith("trustt-"))
            and (d / ".git").exists()
        )
    for name in repos:
        repo_dir = workspace / name
        if repo_dir.is_dir():
            scan_repo(str(repo_dir), result)
    result.http_contracts = build_http_contracts(result)
    result.kafka_contracts = build_kafka_contracts(result)
    return result


def scan_stats(result: ScanResult) -> dict:
    http = result.http_contracts
    kafka = result.kafka_contracts
    money_http = [c for c in http if c.get("money")]
    money_kafka = [c for c in kafka if c.get("money")]
    return {
        "repos_scanned": len(result.requests_by_repo),
        "requests_total": sum(len(v) for v in result.requests_by_repo.values()),
        "unique_requests": len(result.request_owners),
        "api_calls": len(result.api_calls),
        "http_contracts": len(http),
        "kafka_contracts": len(kafka),
        "money_http_contracts": len(money_http),
        "money_kafka_contracts": len(money_kafka),
        "kafka_consumers": len(result.kafka_consumers),
    }


def iter_all_contracts(result: ScanResult) -> Iterator[dict]:
    yield from result.http_contracts
    yield from result.kafka_contracts


def emit_kg_jsonl(result: ScanResult) -> Iterator[dict]:
    """Emit KG nodes/edges for contract layer."""
    for c in iter_all_contracts(result):
        cid = c["id"]
        yield {
            "t": "node",
            "id": cid,
            "kind": "contract",
            "label": cid.split(":", 2)[-1][:120],
            "protocol": c["protocol"],
            "money": c.get("money", False),
            "repo": c["producer"].get("service") or c["consumer"].get("service"),
            "src": c.get("src", ""),
        }
        prod_req = c["producer"].get("request")
        cons_req = c["consumer"].get("request")
        if prod_req:
            yield {
                "t": "edge",
                "from": f"request:{prod_req}",
                "to": cid,
                "rel": "produces_contract",
                "src": c.get("src", ""),
            }
        if cons_req:
            yield {
                "t": "edge",
                "from": cid,
                "to": f"request:{cons_req}",
                "rel": "consumes_via",
                "src": c.get("src", ""),
            }
        ps = c["producer"].get("service")
        cs = c["consumer"].get("service")
        if ps and cs and ps != "?":
            yield {
                "t": "edge",
                "from": f"service:{ps}",
                "to": f"service:{cs}",
                "rel": "contract",
                "note": f"{c['protocol']} {prod_req or c['producer'].get('topic_prefix','')} → {cons_req or c['consumer'].get('bean','')}",
                "src": c.get("src", ""),
            }
