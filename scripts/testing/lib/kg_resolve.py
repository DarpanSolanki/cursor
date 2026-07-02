"""Resolve apiName → service, repo, template, batch flag via KG + filesystem."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from .paths import ROOT

KG_DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"

REPO_TO_SERVICE: dict[str, str] = {
    "novopay-platform-accounting-v2": "accounting",
    "novopay-platform-actor": "actor",
    "novopay-platform-payments": "payments",
    "novopay-platform-batch": "batch",
    "novopay-platform-task": "task",
    "novopay-mfi-los": "los",
}

# Request field → registry _correlators key
FIELD_CORRELATORS: dict[str, str] = {
    "account_number": "ACCOUNT_NUMBER",
    "account_number_list": "ACCOUNT_NUMBER",
    "user_id": "USER_ID",
    "employee_id": "USER_ID",
    "loan_account_id": "LOAN_ACCOUNT_ID",
    "customer_id": "CUSTOMER_ID",
    "lan": "ACCOUNT_NUMBER",
    "loan_account_number": "ACCOUNT_NUMBER",
    "ids": "OFFICE_ID",
    "office_id": "OFFICE_ID",
    "foreclosure_date": "FORECLOSURE_DATE",
    "simulation_date": "FORECLOSURE_DATE",
}


def is_batch_api(api_name: str) -> bool:
    n = api_name or ""
    low = n.lower()
    if low in ("dpiaccrualcalculation", "dpiaccrualbooking", "dpibilling"):
        return True
    return (
        n.endswith("Job")
        or n.endswith("Batch")
        or n.endswith("Calculation")
        or n.endswith("Booking")
        or n.endswith("Billing")
        or "EOD" in n
        or n.startswith("run")
    )


def kg_request(api_name: str) -> dict[str, Any] | None:
    if not KG_DB.is_file():
        return None
    c = sqlite3.connect(str(KG_DB))
    row = c.execute("SELECT json FROM nodes WHERE id=?", (f"request:{api_name}",)).fetchone()
    c.close()
    if not row:
        return None
    return json.loads(row[0])


def find_request_template(repo: str, api_name: str) -> Path | None:
    base = ROOT / repo / "deploy" / "application" / "templates" / "request"
    if not base.is_dir():
        return None
    hits = list(base.rglob(f"{api_name}_requestTemplate.json"))
    return hits[0] if hits else None


def minimal_request_from_template(path: Path, api_name: str, correlators: dict[str, str]) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    root = data.get(api_name) if isinstance(data.get(api_name), dict) else data
    body: dict[str, Any] = {}
    for field, spec in root.items():
        if not isinstance(spec, dict):
            continue
        ck = FIELD_CORRELATORS.get(field)
        val = correlators.get(ck, "1") if ck else "1"
        if spec.get("type") == "ARR":
            body[field] = [val]
        elif spec.get("class") == "SMPL":
            body[field] = val
    return body


def resolve_api(api_name: str, correlators: dict[str, str]) -> dict[str, Any]:
    """Full resolution for autonomous test."""
    meta = kg_request(api_name)
    if not meta:
        raise LookupError(f"apiName '{api_name}' not in KG — run kg-switch after checkout, then build.sh")
    repo = meta.get("repo") or ""
    service = REPO_TO_SERVICE.get(repo)
    if not service:
        # heuristic from repo name
        if "actor" in repo:
            service = "actor"
        elif "accounting" in repo:
            service = "accounting"
        else:
            service = "accounting"
    batch = is_batch_api(api_name)
    tpl = find_request_template(repo, api_name)
    request_body: dict[str, Any] = {}
    if tpl and not batch:
        request_body = minimal_request_from_template(tpl, api_name, correlators)
    return {
        "api_name": api_name,
        "repo": repo,
        "service": service,
        "src": meta.get("src"),
        "is_batch": batch,
        "template": str(tpl) if tpl else None,
        "request": request_body,
    }


def registry_match(reg: dict[str, Any], api_name: str) -> str | None:
    for cid, case in reg.items():
        if case.get("api") == api_name or case.get("api_name") == api_name:
            return cid
    return None
