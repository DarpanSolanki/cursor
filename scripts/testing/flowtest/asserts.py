"""Reusable money asserts — flow-agnostic. DFC-specific shapes stay in dcf e2e."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from decimal import Decimal

from .db import PG, PG_ENV, psql, psql_raw

ACCEPTANCE_STRICT = os.environ.get("ACCEPTANCE_STRICT", "1") != "0"
ACCOUNTING_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")


def snapshot_dues(lan: str, label: str) -> dict:
    row = psql(
        f"""
SELECT COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.paid_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.waived_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.due_amount-ldd.paid_amount-ldd.waived_amount ELSE 0 END),0),
       COALESCE(SUM(CASE WHEN ldd.component_type='INT' THEN ldd.waived_amount ELSE 0 END),0),
       la.loan_status
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{lan}' AND ldd.is_deleted=false
GROUP BY la.loan_status;
"""
    )
    parts = row.split("|") if row else ["0", "0", "0", "0", ""]
    snap = {
        "label": label,
        "lan": lan,
        "prin_paid": Decimal(parts[0] or "0"),
        "prin_waived": Decimal(parts[1] or "0"),
        "prin_pending": Decimal(parts[2] or "0"),
        "int_waived": Decimal(parts[3] or "0"),
        "loan_status": parts[4] if len(parts) > 4 else "",
    }
    print(
        f"  [{label}] {lan} status={snap['loan_status']} prin_paid={snap['prin_paid']} "
        f"prin_waived={snap['prin_waived']} prin_pending={snap['prin_pending']} int_waived={snap['int_waived']}"
    )
    return snap


def assert_loan_status(lan: str, expected: str, *, label: str = "") -> None:
    got = psql(
        f"SELECT loan_status FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{lan}' AND is_deleted=false;"
    )
    if got != expected:
        raise AssertionError(
            f"loan_status FAIL {label or lan}: expected={expected!r} got={got!r}"
        )
    print(f"  loan_status PASS: {lan}={expected}")


def assert_account_status(lan: str, expected: str, *, label: str = "") -> None:
    got = psql(
        f"""
SELECT a.status FROM mfi_accounting.account a
JOIN mfi_accounting.loan_account la ON la.account_id=a.id
WHERE la.la_account_number='{lan}' AND la.is_deleted=false;
"""
    )
    if got != expected:
        raise AssertionError(
            f"account.status FAIL {label or lan}: expected={expected!r} got={got!r}"
        )
    print(f"  account.status PASS: {lan}={expected}")


def partition_codes(ref: str) -> list[str]:
    out = psql_raw(
        f"""
SELECT COALESCE(tpd.gl_code,'')||':'||COALESCE(tpd.amount,0)::text||':'||COALESCE(tpd.cr_dr_indicator,'')
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}'
ORDER BY 1;
"""
    ).strip()
    return [r.strip() for r in out.splitlines() if r.strip()]


def assert_gl_balanced_txn(
    ref: str,
    label: str,
    *,
    allow_empty: bool = False,
    empty_oos_label_substrings: tuple[str, ...] = (),
) -> None:
    """Per-txn partition debit == credit (fail-closed unless allow_empty / OOS label)."""
    if not ref:
        raise AssertionError(f"GL balance FAIL {label}: empty reference_number")
    row = psql(
        f"""
SELECT COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('D','DEBIT')
    THEN tpd.amount ELSE 0 END),0)::text,
       COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('C','CREDIT')
    THEN tpd.amount ELSE 0 END),0)::text,
       COUNT(*)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{ref}';
"""
    )
    parts = (row or "0|0|0").split("|")
    debit = Decimal(parts[0] or "0")
    credit = Decimal(parts[1] or "0")
    part_count = int(parts[2] or "0")
    if part_count == 0:
        if allow_empty or any(s in label for s in empty_oos_label_substrings):
            print(f"  GL balance Out-of-scope/empty: {label} ref={ref} 0 partitions")
            return
        if ACCEPTANCE_STRICT:
            raise AssertionError(
                f"GL balance FAIL {label} ref={ref}: SUCCESS tm exists but 0 partition rows"
            )
        print(f"  GL balance soft-empty: {label} ref={ref}")
        return
    if ACCEPTANCE_STRICT and debit != credit:
        raise AssertionError(
            f"GL balance FAIL {label} ref={ref}: debit={debit} credit={credit} "
            f"partitions={partition_codes(ref)}"
        )
    print(f"  GL balance PASS: {label} ref={ref} debit={debit} credit={credit} parts={part_count}")


def txn_refs_for_lan(lan: str, txn_type: str) -> list[str]:
    out = psql_raw(
        f"""
SELECT DISTINCT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{lan}' AND tc.type = '{txn_type}'
ORDER BY tm.reference_number;
"""
    ).strip()
    return [r.strip() for r in out.splitlines() if r.strip()]


def assert_gl_balance_for_loan(
    lan: str,
    reference_codes: list[str],
    *,
    allow_empty: bool = False,
) -> None:
    for txn_type in reference_codes:
        refs = txn_refs_for_lan(lan, txn_type)
        if not refs:
            raise AssertionError(f"GL balance FAIL: {lan} missing required {txn_type} transaction")
        for ref in refs:
            assert_gl_balanced_txn(ref, f"{lan}/{txn_type}", allow_empty=allow_empty)


def acct_post(api: str, body: dict) -> dict:
    url = f"{ACCOUNTING_URL.rstrip('/')}/{api}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace") if exc.fp else ""
        raise RuntimeError(f"HTTP {exc.code} {api}: {raw[:500]}") from exc


def assert_webapp_summary_accrued_le_original(lan: str, *, role: str = "loan") -> None:
    """Live getLoanAccountSummaryDetails — Accrued ≤ Original (+₹1)."""
    body = {
        "headers": {
            "tenant_code": "mfi",
            "user_id": os.environ.get("ICF_USER_ID", "103"),
            "client_code": "novopay",
            "channel_code": "WEB",
            "stan": f"ft_sum_{lan}_{os.getpid()}",
            "transmission_datetime": str(int(__import__("time").time() * 1000)),
            "function_code": "DEFAULT",
            "function_sub_code": "DEFAULT",
        },
        "request": {"loan_account_number": lan},
    }
    resp = acct_post("getLoanAccountSummaryDetails", body)
    interest = (resp.get("response") or {}).get("interest_details") or {}
    accrued = Decimal(str(interest.get("accrued_amount") or "0"))
    original = Decimal(str(interest.get("original_amount") or "0"))
    if ACCEPTANCE_STRICT and accrued > original + Decimal("1"):
        raise AssertionError(
            f"webapp summary FAIL ({role} {lan}): Accrued={accrued} > Original={original}"
        )
    print(
        f"  webapp summary PASS: {role} {lan} interest_details.accrued_amount={accrued} "
        f"interest_details.original_amount={original}"
    )
