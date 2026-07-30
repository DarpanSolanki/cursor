#!/usr/bin/env python3
"""Loan product taxonomy — code-backed facts for KG + flowtest fixture validation.

Sources (trustt-platform-accounting):
  GetLoanAccountBasicDetailsProcessor LOAN_SHG / LOAN_JLG / LOAN_IND
  loan_account.has_child_accounts + parent_loan_account_id (LoanAccountRepository)
  group_mfi_orc.xml childLoan* Requests (SHG group parent flows only)
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CURATED = ROOT / "cursor-bundle/kg/curated/loan_taxonomy.json"
PROVENANCE = {
    "LOAN_SHG": "GetLoanAccountBasicDetailsProcessor.java:22; CreateMandateDetailsProcessor.java:59; loan_account.has_child_accounts",
    "LOAN_JLG": "GetLoanAccountBasicDetailsProcessor.java:21; ValidateMandateDetailsForCreateProcessor.java:51 (single LAN per member)",
    "LOAN_IND": "GetLoanAccountBasicDetailsProcessor.java:23",
    "child_flows": "group_mfi_orc.xml childLoan* Requests; LoanAccountEventsQueueEntity EVENT_TYPE_ORC_API_MAP",
}

TAXONOMY: dict[str, dict[str, Any]] = {
    "LOAN_SHG": {
        "label": "SHG",
        "has_children": True,
        "parent_child_lans": True,
        "child_flows": [
            "childLoanDisbursement",
            "childLoanRepayment",
            "childLoanForeclosure",
            "childLoanRestructuring",
            "childLoanReopening",
            "childLoanTransactionReversal",
            "childLoanPartPrepayment",
            "parentLoanAccountPartPrepayment",
            "childLoanDisbursementCancellation",
            "childLoanAccountExcessAmountRefund",
            "childLoanEventProcessingBatchJob",
            "deathForeclosureInsuranceJob",
        ],
        "invalid_for": [],
    },
    "LOAN_JLG": {
        "label": "JLG",
        "has_children": False,
        "parent_child_lans": False,
        "child_flows": [],
        "invalid_for": [
            "childLoanForeclosure",
            "childLoanRepayment",
            "childLoanDisbursement",
            "parentLoanAccountPartPrepayment",
            "deathForeclosureInsuranceJob",
        ],
    },
    "LOAN_IND": {
        "label": "INDL",
        "has_children": False,
        "parent_child_lans": False,
        "child_flows": [],
        "invalid_for": [
            "childLoanForeclosure",
            "childLoanRepayment",
            "childLoanDisbursement",
            "parentLoanAccountPartPrepayment",
            "deathForeclosureInsuranceJob",
        ],
    },
}

CHILD_SCENARIO_MARKERS = (
    "dcf_group",
    "child",
    "parent_lan",
    "group_parent",
    "DCF_GROUP",
)


def write_curated_facts() -> Path:
    payload = {
        "version": 1,
        "updated": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        ),
        "provenance": PROVENANCE,
        "loan_types": TAXONOMY,
    }
    CURATED.parent.mkdir(parents=True, exist_ok=True)
    CURATED.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return CURATED


def _psql(sql: str) -> str:
    r = subprocess.run(
        [
            "psql",
            "-h",
            "localhost",
            "-p",
            "5433",
            "-U",
            "yugabyte",
            "-d",
            "yugabyte",
            "-t",
            "-A",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            sql,
        ],
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "PGPASSWORD": "yugabyte"},
    )
    if r.returncode != 0:
        return ""
    return (r.stdout or "").strip().split("\n")[0] if r.stdout.strip() else ""


def classify_lan(lan: str) -> dict[str, Any]:
    """Resolve loan_category + has_child_accounts from local DB."""
    row = _psql(
        f"""
SELECT COALESCE(lp.loan_category,''),
       COALESCE(la.has_child_accounts::text,'false'),
       COALESCE(la.parent_loan_account_id::text,'')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
WHERE la.la_account_number = '{lan}' AND la.is_deleted = false;
"""
    )
    if not row:
        return {"lan": lan, "loan_category": "", "has_children": False, "is_child": False, "known": False}
    parts = row.split("|")
    cat = parts[0].strip() if parts else ""
    has_ch = parts[1].strip() if len(parts) > 1 else ""
    parent_id = parts[2].strip() if len(parts) > 2 else ""
    return {
        "lan": lan,
        "loan_category": cat.strip(),
        "has_children": has_ch.strip().lower() in ("t", "true", "1"),
        "is_child": bool(parent_id),
        "known": bool(cat.strip()),
    }


def validate_scenario_fixture(
    *,
    parent_lan: str,
    profile_name: str,
    scenario_name: str = "",
    expects_children: bool | None = None,
) -> str | None:
    """Return refusal reason when fixture LAN type mismatches scenario; None = OK.

    Fail-closed: unknown/unclassifiable LAN refuses child-shaped scenarios
    (never silent None-passthrough for parent+child ops).
    """
    info = classify_lan(parent_lan)
    child_scenario = (
        expects_children
        if expects_children is not None
        else any(m in (profile_name + scenario_name).lower() for m in CHILD_SCENARIO_MARKERS)
    )
    if not info.get("known"):
        if child_scenario or expects_children is True:
            return (
                f"REFUSE: cannot classify fixture LAN {parent_lan!r} "
                f"(unknown/missing) — block child/group scenario "
                f"{profile_name!r}/{scenario_name!r}"
            )
        return (
            f"REFUSE: cannot classify fixture LAN {parent_lan!r} "
            f"(unknown/missing) — fail-closed taxonomy gate"
        )
    cat = str(info.get("loan_category") or "")
    meta = TAXONOMY.get(cat) or {}
    if child_scenario and not meta.get("has_children"):
        return (
            f"REFUSE: scenario expects parent+child LANs but fixture {parent_lan} "
            f"is {meta.get('label', cat)} (has_children=false per code taxonomy)"
        )
    if not child_scenario and meta.get("has_children") and info.get("has_children"):
        # SHG parent on non-child scenario is OK (single-LAN flows on parent still valid)
        return None
    return None


def orient_header(lan: str) -> str:
    """One-line MCP/orient header — no child-flow guidance for JLG/INDL."""
    info = classify_lan(lan)
    cat = str(info.get("loan_category") or "UNKNOWN")
    meta = TAXONOMY.get(cat) or {}
    label = meta.get("label", cat)
    if meta.get("has_children"):
        return f"[LAN {lan} {label} has_children=true — child flows applicable]"
    return f"[LAN {lan} {label} single-LAN — child flows N/A]"
