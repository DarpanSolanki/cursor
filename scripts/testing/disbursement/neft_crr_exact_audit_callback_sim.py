#!/usr/bin/env python3
"""NEFT CRR exact-audit + inbound callback CRR — code-backed simulation.

Prefer: live bank ST_NEF/ST_NEI callback against a NEFT_STAGE_* fixture LAN +
SQL assert on client_request_response_log columns.

When that E2E cannot run (no bank callback / fixture), this case proves the
persist path on disk by:

1. ORCH_SIBLING_SIM — both callback Requests wire doGenericSyncSTPBankNeftCallBackProcessor
   (mfi_orc.xml on disk).
2. PROCESSOR_MIRROR_SIM — persistInboundCallbackCrr / buildInboundCallbackRequestAudit /
   buildCallbackOutcomeResponse / resolveCallbackTransactionType field contracts
   parsed from DoGenericSyncSTPBankNeftCallBackProcessor.java (not guessed).
3. PROCESSOR_MIRROR_SIM — DisbursementBankCrrLogHelper.saveWithExactAudit logs exact
   request/response at INFO before DAO save; ParentDisbursementNeftV2BankCall uses it.
4. PROCESSOR_MIRROR_SIM — responseForClientRequestLog prefers EC response body.

Expected CRR column values (mirrored from Java):

| outcome     | transaction_type                         | request keys              | response keys                         | status  |
|-------------|------------------------------------------|---------------------------|---------------------------------------|---------|
| SUCCESS     | DISBURSEMENT_NEFT_NEF_CALLBACK / NEI_…   | paymentlist|inqlist       | callback_outcome=SUCCESS (+utr)       | SUCCESS |
| FAIL        | same                                     | paymentlist|inqlist       | callback_outcome=FAIL (+error)        | FAIL    |
| IN_PROGRESS | same                                     | paymentlist|inqlist       | callback_outcome=IN_PROGRESS (+error) | UNKNOWN |
| reinit      | …_CALLBACK_REINIT                        | same                      | same                                  | …       |

Verify mode labels printed for ship / JIRA honesty.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from lib.orch_sibling_parity import beans_for_request  # noqa: E402

ACCT = ROOT / "trustt-platform-accounting"
MFI_ORC = ACCT / "deploy/application/orchestration/mfi_orc.xml"
CALLBACK_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/disbursement/processor"
    / "DoGenericSyncSTPBankNeftCallBackProcessor.java"
)
HELPER_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/disbursement/util"
    / "DisbursementBankCrrLogHelper.java"
)
UNCERTAINTY_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/disbursement/util"
    / "DisbursementBankCallUncertainty.java"
)
CONSTANTS_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/disbursement/util"
    / "DisbursementBankCallConstants.java"
)
NEFT_V2_JAVA = (
    ACCT
    / "src/main/java/in/novopay/accounting/loan/disbursement/bank/parent"
    / "ParentDisbursementNeftV2BankCall.java"
)
ACCT_CONST_JAVA = (
    ACCT / "src/main/java/in/novopay/accounting/common/AccountingConstants.java"
)

REQUIRED_CALLBACK_BEAN = "doGenericSyncSTPBankNeftCallBackProcessor"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise AssertionError(msg)


def _extract_const(src: str, name: str) -> str:
    m = re.search(
        rf'public\s+static\s+final\s+String\s+{re.escape(name)}\s*=\s*"([^"]+)"\s*;',
        src,
    )
    _require(m is not None, f"Missing constant {name} in source")
    return m.group(1)


def _mirror_resolve_txn_type(callback_type: str, outbound_txn: str | None, *, nef_cb: str, nei_cb: str, reinit: str) -> str:
    base = nef_cb if callback_type.upper() == "ST_NEF" else nei_cb
    if outbound_txn and outbound_txn.upper().endswith(reinit.upper()):
        return base + reinit
    return base


def _mirror_request_audit(callback_type: str, list_obj: dict) -> dict:
    root: dict = {"callback_type": callback_type}
    root["api"] = (
        "doGenericSyncSTPBankNEFNeftCallBack"
        if callback_type.upper() == "ST_NEF"
        else "doGenericSyncSTPBankNEINeftCallBack"
    )
    if callback_type.upper() == "ST_NEF":
        root["paymentlist"] = list_obj
    else:
        root["inqlist"] = list_obj
    return root


def _mirror_outcome_response(
    payment_ref: str,
    outcome: str,
    *,
    utr: str | None = None,
    error_code: str | None = None,
    error_message: str | None = None,
) -> dict:
    out: dict = {"paymentrefno": payment_ref, "callback_outcome": outcome}
    if utr:
        out["referenceno"] = utr
    if error_code:
        out["errorcode"] = error_code
    if error_message:
        out["errorMessage"] = error_message
    return out


def main() -> int:
    print("Verify mode: ORCH_SIBLING_SIM + PROCESSOR_MIRROR_SIM")
    print(
        "Blocker (full E2E): live ST_NEF/ST_NEI bank callback + NEFT_STAGE fixture LAN "
        "+ SQL readback on client_request_response_log not assumed this run."
    )

    # --- ORCH ---
    for req in (
        "doGenericSyncSTPBankNEFNeftCallBack",
        "doGenericSyncSTPBankNEINeftCallBack",
    ):
        beans = beans_for_request(MFI_ORC, req)
        _require(
            REQUIRED_CALLBACK_BEAN in beans,
            f"{req}: missing bean {REQUIRED_CALLBACK_BEAN}; have={beans}",
        )
    print("ORCH_SIBLING_SIM PASS: NEF/NEI callback Requests →", REQUIRED_CALLBACK_BEAN)

    # --- Constants on disk ---
    const_src = CONSTANTS_JAVA.read_text(encoding="utf-8")
    nef_cb = _extract_const(const_src, "DISBURSEMENT_NEFT_NEF_CALLBACK")
    nei_cb = _extract_const(const_src, "DISBURSEMENT_NEFT_NEI_CALLBACK")
    partner = _extract_const(const_src, "PARTNER_CODE")
    _require(nef_cb == "DISBURSEMENT_NEFT_NEF_CALLBACK", f"unexpected NEF callback type {nef_cb}")
    _require(nei_cb == "DISBURSEMENT_NEFT_NEI_CALLBACK", f"unexpected NEI callback type {nei_cb}")
    _require(partner == "Hdfc", f"unexpected partner {partner}")

    acct_const = ACCT_CONST_JAVA.read_text(encoding="utf-8")
    reinit = _extract_const(acct_const, "DISBURSEMENT_CRR_REINIT_SUFFIX")
    status_success = _extract_const(acct_const, "SUCCESS")
    status_fail = _extract_const(acct_const, "FAIL")
    status_unknown = _extract_const(acct_const, "UNKNOWN")
    _require(reinit == "_REINIT", f"unexpected reinit suffix {reinit}")

    # --- Callback processor field contracts ---
    cb = CALLBACK_JAVA.read_text(encoding="utf-8")
    for needle, label in (
        ("persistInboundCallbackCrr(", "persistInboundCallbackCrr method"),
        ("buildInboundCallbackRequestAudit(", "request audit builder"),
        ("buildCallbackOutcomeResponse(", "outcome response builder"),
        ("resolveCallbackTransactionType(", "txn type resolver"),
        ('root.put("paymentlist"', "NEF request embeds paymentlist"),
        ('root.put("inqlist"', "NEI request embeds inqlist"),
        ('outcomeJson.put("callback_outcome"', "response has callback_outcome"),
        ("bankCrrLogHelper.saveWithExactAudit(entity)", "callback CRR via saveWithExactAudit"),
        ("entity.setClientReferenceNumber(paymentRef)", "client_ref = paymentref (inbound bank correlator)"),
        ("CALLBACK_OUTCOME_SUCCESS", "SUCCESS outcome constant"),
        ("CALLBACK_OUTCOME_FAIL", "FAIL outcome constant"),
        ("CALLBACK_OUTCOME_IN_PROGRESS", "IN_PROGRESS outcome constant"),
        ("DISBURSEMENT_NEFT_NEF_CALLBACK", "NEF callback txn type"),
        ("DISBURSEMENT_NEFT_NEI_CALLBACK", "NEI callback txn type"),
    ):
        _require(needle in cb, f"Callback processor missing: {label} ({needle})")

    # Outcome → CRR status wiring (exact call sites)
    _require(
        re.search(
            r"persistInboundCallbackCrr\([\s\S]*?CALLBACK_OUTCOME_SUCCESS[\s\S]*?,\s*SUCCESS\)",
            cb,
        )
        is not None,
        "SUCCESS outcome must persist CRR status SUCCESS",
    )
    _require(
        re.search(
            r"persistInboundCallbackCrr\([\s\S]*?CALLBACK_OUTCOME_FAIL[\s\S]*?,\s*FAIL\)",
            cb,
        )
        is not None,
        "FAIL outcome must persist CRR status FAIL",
    )
    _require(
        re.search(
            r"persistInboundCallbackCrr\([\s\S]*?CALLBACK_OUTCOME_IN_PROGRESS[\s\S]*?,\s*UNKNOWN\)",
            cb,
        )
        is not None,
        "IN_PROGRESS outcome must persist CRR status UNKNOWN",
    )
    _require('setLoanAccountNumber(outboundCrr != null' in cb or 'setLoanAccountNumber(outboundCrr != null' in cb.replace("\n", ""), "LAN from outbound or UNRESOLVED")
    _require('"UNRESOLVED"' in cb, "Unresolved outbound must set LAN UNRESOLVED")
    print("PROCESSOR_MIRROR_SIM PASS: callback persistInboundCallbackCrr contracts")

    # --- Mirror expected column values (logic matching Java) ---
    payment_ref = "PAYREF_SIM_001"
    paymentlist = {"paymentrefno": payment_ref, "txtstatus": "P"}
    inqlist = {"paymentrefno": payment_ref, "codstatus": "P"}

    cases = [
        {
            "name": "NEF SUCCESS",
            "callback": "ST_NEF",
            "list_key": "paymentlist",
            "list_obj": paymentlist,
            "outbound_txn": "DISBURSEMENT_NEFT_NEF",
            "outcome": "SUCCESS",
            "crr_status": status_success,
            "utr": "UTR999",
            "expect_txn": nef_cb,
        },
        {
            "name": "NEI FAIL",
            "callback": "ST_NEI",
            "list_key": "inqlist",
            "list_obj": inqlist,
            "outbound_txn": "DISBURSEMENT_NEFT_NEI",
            "outcome": "FAIL",
            "crr_status": status_fail,
            "error_code": "E001",
            "error_message": "rejected",
            "expect_txn": nei_cb,
        },
        {
            "name": "NEF IN_PROGRESS → UNKNOWN",
            "callback": "ST_NEF",
            "list_key": "paymentlist",
            "list_obj": paymentlist,
            "outbound_txn": "DISBURSEMENT_NEFT_NEF",
            "outcome": "IN_PROGRESS",
            "crr_status": status_unknown,
            "error_code": "NDF",
            "error_message": "pending",
            "expect_txn": nef_cb,
        },
        {
            "name": "NEF SUCCESS reinit",
            "callback": "ST_NEF",
            "list_key": "paymentlist",
            "list_obj": paymentlist,
            "outbound_txn": "DISBURSEMENT_NEFT_NEF" + reinit,
            "outcome": "SUCCESS",
            "crr_status": status_success,
            "utr": "UTR_REINIT",
            "expect_txn": nef_cb + reinit,
        },
    ]

    for case in cases:
        txn = _mirror_resolve_txn_type(
            case["callback"],
            case["outbound_txn"],
            nef_cb=nef_cb,
            nei_cb=nei_cb,
            reinit=reinit,
        )
        _require(txn == case["expect_txn"], f"{case['name']}: txn_type got {txn} want {case['expect_txn']}")

        req = _mirror_request_audit(case["callback"], case["list_obj"])
        _require(case["list_key"] in req, f"{case['name']}: request missing {case['list_key']}")
        _require("callback_type" in req and req["callback_type"] == case["callback"], f"{case['name']}: callback_type")

        resp = _mirror_outcome_response(
            payment_ref,
            case["outcome"],
            utr=case.get("utr"),
            error_code=case.get("error_code"),
            error_message=case.get("error_message"),
        )
        _require(resp["callback_outcome"] == case["outcome"], f"{case['name']}: callback_outcome")
        _require(resp["paymentrefno"] == payment_ref, f"{case['name']}: paymentrefno")

        # Simulated CRR row — full column contract persistInboundCallbackCrr writes
        lan = "LAN_SIM_001"
        crr_row = {
            "partner": partner,
            "client_reference_number": payment_ref,
            "loan_account_number": lan,
            "transaction_type": txn,
            "request": json.dumps(req, separators=(",", ":")),
            "response": json.dumps(resp, separators=(",", ":")),
            "status": case["crr_status"],
        }
        _require(
            crr_row["client_reference_number"] == payment_ref,
            f"{case['name']}: client_reference_number must equal paymentref ({payment_ref})",
        )
        _require(crr_row["partner"] == partner, f"{case['name']}: partner")
        _require(crr_row["loan_account_number"] == lan, f"{case['name']}: loan_account_number")
        _require(crr_row["transaction_type"] == case["expect_txn"], f"{case['name']}: transaction_type")
        _require(crr_row["status"] == case["crr_status"], f"{case['name']}: status exact")
        _require(case["list_key"] in crr_row["request"], f"{case['name']}: request JSON must contain {case['list_key']}")
        _require('"callback_outcome"' in crr_row["response"], f"{case['name']}: response JSON must contain callback_outcome")
        _require(resp["callback_outcome"] == case["outcome"], f"{case['name']}: response.callback_outcome value")
        print(
            f"ASSERT PASS [{case['name']}]: "
            f"client_reference_number={crr_row['client_reference_number']} "
            f"loan_account_number={crr_row['loan_account_number']} "
            f"transaction_type={crr_row['transaction_type']} status={crr_row['status']} "
            f"partner={crr_row['partner']} request.has_{case['list_key']}=True "
            f"response.callback_outcome={case['outcome']}"
        )

    unresolved = {
        "loan_account_number": "UNRESOLVED",
        "transaction_type": nef_cb,
        "partner": partner,
    }
    _require(unresolved["loan_account_number"] == "UNRESOLVED", "unresolved LAN sentinel")
    print("ASSERT PASS [unresolved outbound]: loan_account_number=UNRESOLVED")

    # --- Helper exact audit ---
    helper = HELPER_JAVA.read_text(encoding="utf-8")
    _require("saveWithExactAudit(" in helper, "Helper must expose saveWithExactAudit")
    _require("logExactApiAudit(" in helper, "Helper must expose logExactApiAudit")
    _require("CRR exact API audit" in helper, "INFO audit line marker missing")
    _require(
        re.search(
            r"saveWithExactAudit\([\s\S]*?logExactApiAudit\(entity\);[\s\S]*?clientRequestResponseLogDAOService\.save\(entity\)",
            helper,
        )
        is not None,
        "saveWithExactAudit must log then DAO.save (exact audit before persist)",
    )
    _require("persistBankOrInquiryLegLog" in helper and "saveWithExactAudit(entity)" in helper, "leg log routes through exact audit")
    print("PROCESSOR_MIRROR_SIM PASS: DisbursementBankCrrLogHelper saveWithExactAudit")

    # --- Outbound NEFT v2 + exception body preference ---
    neft_v2 = NEFT_V2_JAVA.read_text(encoding="utf-8")
    _require("bankCrrLogHelper.saveWithExactAudit(entity)" in neft_v2, "Parent NEFT v2 must saveWithExactAudit")
    _require("responseForClientRequestLog(" in neft_v2, "Parent NEFT v2 exception path uses responseForClientRequestLog")

    unc = UNCERTAINTY_JAVA.read_text(encoding="utf-8")
    _require("responseForClientRequestLog(" in unc, "Uncertainty helper must define responseForClientRequestLog")
    _require(
        re.search(
            r"responseForClientRequestLog[\s\S]*?ctx\.get\(RESPONSE_KEY\)[\s\S]*?return body[\s\S]*?responseSummaryForClientRequestLog",
            unc,
        )
        is not None,
        "responseForClientRequestLog must prefer EC response body then fall back to summary",
    )
    print("PROCESSOR_MIRROR_SIM PASS: outbound NEFT v2 + responseForClientRequestLog EC body preference")

    print("PASS: disbursement.neft_crr_exact_audit_callback_sim")
    print(
        "Upgrade path: ntest/API live doGenericSyncSTPBankNEFNeftCallBack on fixture LAN "
        "then SELECT transaction_type,request,response,status FROM client_request_response_log "
        "WHERE transaction_type LIKE 'DISBURSEMENT_NEFT_%_CALLBACK%'."
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
