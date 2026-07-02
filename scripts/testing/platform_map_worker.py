#!/usr/bin/env python3
"""Platform map workers — extract all requests, loan flows, batch jobs, Kafka (stdlib)."""

from __future__ import annotations

import glob
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

# Import shared scanner
import sys

BIN = Path(__file__).resolve().parents[2] / "cursor-bundle/kg/bin"
sys.path.insert(0, str(BIN))

from _contract_scan import (  # noqa: E402
    BEAN_RE,
    PRODUCER_ID_RE,
    REQ_RE,
    TOPIC_RE,
    is_money,
    orchestration_xmls,
    repo_name,
    scan_workspace,
)
from _paths import WORKSPACE  # noqa: E402

FLOW_TEST = WORKSPACE / "cursor-bundle/flow-test"

LOAN_PAT = re.compile(
    r"loan|disburse|repay|foreclos|prepay|mandate|installment|due|dpd|billing|accrual|"
    r"dpi|writeoff|cancellation|reversal|collection|portfolio|death|insurance|"
    r"partprepay|asset|npa|foreclos|booking|restructur|childloan|si|enach|noc|refund|excess",
    re.I,
)
BATCH_PAT = re.compile(r"Job$|Batch$|BatchJob$|Calculation$|Booking$|Billing$", re.I)
GL_PAT = re.compile(r"general.?ledger|glbalance|trialbalance|journal|posting|transaction.?catalogue", re.I)
PRODUCT_PAT = re.compile(r"product|scheme|charge|interest.?rate|price", re.I)
GROUP_PAT = re.compile(r"group|shg|jlg|center|meeting", re.I)
READ_PAT = re.compile(r"^(get|fetch|list|search|view|download|export)", re.I)

BEAN_NAME_RE = re.compile(r'@Bean\s*\(\s*name\s*=\s*"([^"]+)"')


def categorize_request(name: str, repo: str) -> str:
    if BATCH_PAT.search(name):
        return "batch_job"
    if LOAN_PAT.search(name):
        return "loan_account"
    if GL_PAT.search(name):
        return "general_ledger"
    if PRODUCT_PAT.search(name):
        return "product_config"
    if GROUP_PAT.search(name) and "novopay-mfi-los" in repo:
        return "los_group"
    if READ_PAT.search(name):
        return "read_api"
    if "payment" in repo or "collection" in name.lower():
        return "collections"
    if "actor" in repo:
        return "actor_org"
    if "task" in repo:
        return "task_workflow"
    if "approval" in repo or name == "submitApplication":
        return "approval"
    if "notification" in repo:
        return "notification"
    if "masterdata" in repo:
        return "masterdata"
    if "authorization" in repo:
        return "authorization"
    if "audit" in repo:
        return "audit"
    if "report" in repo:
        return "reporting"
    return "other"


def scan_all_requests() -> list[dict]:
    result = scan_workspace(WORKSPACE)
    rows: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for req, owners in sorted(result.request_owners.items()):
        for repo in sorted(owners):
            key = (repo, req)
            if key in seen:
                continue
            seen.add(key)
            cat = categorize_request(req, repo)
            rows.append({
                "id": f"api:{repo}:{req}",
                "request": req,
                "repo": repo,
                "category": cat,
                "money": is_money(req) or cat in ("loan_account", "batch_job", "collections", "general_ledger"),
                "kg_request": f"request:{req}",
                "owners": sorted(owners),
                "multi_service": len(owners) > 1,
            })
    return rows


def scan_batch_jobs_java() -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for repo_dir in WORKSPACE.glob("novopay-*"):
        if not (repo_dir / ".git").is_dir():
            continue
        repo = repo_dir.name
        for path in repo_dir.rglob("*.java"):
            if "test" in path.parts:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if "@Bean" not in text and "BatchConfig" not in path.name and "JobLoader" not in path.name:
                continue
            rel = path.relative_to(WORKSPACE)
            for m in BEAN_NAME_RE.finditer(text):
                name = m.group(1)
                if name in seen:
                    continue
                seen.add(name)
                rows.append({
                    "id": f"job:{repo}:{name}",
                    "job_name": name,
                    "repo": repo,
                    "category": "batch_job",
                    "money": bool(LOAN_PAT.search(name) or BATCH_PAT.search(name)),
                    "src": str(rel),
                    "request": name if orchestration_has_request(name) else None,
                })
    return rows


def orchestration_has_request(name: str) -> bool:
    pat = re.compile(rf'name="{re.escape(name)}"')
    for repo_dir in WORKSPACE.glob("novopay-*"):
        for xml in orchestration_xmls(str(repo_dir)):
            try:
                if pat.search(Path(xml).read_text(encoding="utf-8", errors="replace")):
                    return True
            except OSError:
                pass
    return False


def scan_kafka_index() -> list[dict]:
    consumer_block = re.compile(r"<Consumer>(.*?)</Consumer>", re.S)
    rows: list[dict] = []
    for repo_dir in WORKSPACE.glob("novopay-*"):
        if not (repo_dir / ".git").is_dir():
            continue
        repo = repo_dir.name
        for path in repo_dir.rglob("MessageBroker.xml"):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            rel = path.relative_to(WORKSPACE)
            for block in consumer_block.finditer(text):
                body = block.group(1)
                tm = TOPIC_RE.search(body)
                bm = BEAN_RE.search(body)
                if tm and bm:
                    topic = tm.group(1).strip()
                    rows.append({
                        "id": f"kafka:{repo}:{topic}",
                        "topic_prefix": topic,
                        "consumer_bean": bm.group(1).strip(),
                        "repo": repo,
                        "protocol": "KAFKA",
                        "money": is_money(topic, bm.group(1)),
                        "src": str(rel),
                    })
            for pid in PRODUCER_ID_RE.finditer(text):
                topic = pid.group(1).strip()
                rows.append({
                    "id": f"kafka-producer:{repo}:{topic}",
                    "topic_prefix": topic,
                    "repo": repo,
                    "protocol": "KAFKA_PRODUCER",
                    "money": is_money(topic),
                    "src": str(rel),
                })
    return rows


def build_loan_flows(platform_rows: list[dict], batch_rows: list[dict]) -> list[dict]:
    loan: list[dict] = []
    for r in platform_rows:
        if r["category"] == "loan_account" or (r.get("money") and r["category"] in ("batch_job", "collections")):
            loan.append({**r, "flow_type": "loan_account"})
    for r in batch_rows:
        if r.get("money") or LOAN_PAT.search(r["job_name"]):
            loan.append({
                "id": r["id"],
                "request": r.get("request") or r["job_name"],
                "repo": r["repo"],
                "category": "batch_job",
                "money": True,
                "flow_type": "batch_job",
                "job_name": r["job_name"],
                "src": r.get("src"),
            })
    return loan


def write_jsonl(path: Path, header: str, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# {header}"]
    for row in rows:
        lines.append(json.dumps(row, separators=(",", ":")))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def run_platform_map() -> dict:
    platform = scan_all_requests()
    jobs = scan_batch_jobs_java()
    kafka = scan_kafka_index()
    loan = build_loan_flows(platform, jobs)

    write_jsonl(FLOW_TEST / "platform_map.jsonl", "All orchestration requests (all repos)", platform)
    write_jsonl(FLOW_TEST / "loan_flows.jsonl", "Loan account + money batch flows", loan)
    write_jsonl(FLOW_TEST / "batch_jobs.jsonl", "Spring batch @Bean job names", jobs)
    write_jsonl(FLOW_TEST / "kafka_index.jsonl", "Kafka consumers + producers", kafka)

    by_cat = defaultdict(int)
    for r in platform:
        by_cat[r["category"]] += 1
    return {
        "platform_requests": len(platform),
        "loan_flows": len(loan),
        "batch_jobs": len(jobs),
        "kafka_entries": len(kafka),
        "categories": dict(by_cat),
    }


if __name__ == "__main__":
    print(json.dumps(run_platform_map(), indent=2))
