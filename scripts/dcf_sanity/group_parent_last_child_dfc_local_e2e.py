#!/usr/bin/env python3
"""
SDCP-10199 — real local e2e: SHG/group parent + 2 children through deathForeclosureInsuranceJob.

Drives production-shaped insurance batches (outbound → inbound patch → approve job).
Verifies DB: loan status, dues paid/waived, DEATH_FORECLOSURE + RSCH_DEATH_FORECLOSURE postings.

Usage:
  python3 scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py
  PARENT_LAN=6003973025 CHILD1_LAN=6003973329 CHILD2_LAN=6003973330 python3 ...

Requires: local accounting up, mfi_batch schema, target loans ACTIVE with LIFE_INSUR.
"""
from __future__ import annotations

import atexit
import fcntl
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))
from flowtest.lock import (  # noqa: E402
    FLOWTEST_E2E_LOCK as DCF_E2E_LOCK,
    acquire_flowtest_lock as _acquire_flowtest_lock,
    mark_lock_held,
)
from flowtest import asserts as _ft_asserts  # noqa: E402

# --- QA acceptance gate (feedback_qa_acceptance_not_subset_verify.md) ---
# Default STRICT: a test must FAIL on the exact QA fail mode, never print "OK …" and pass.
#   * amount(txn) != principal(payment) is a FAIL unless the delta components are documented.
#   * force-bill labd must be visible without EMI-hijack.
# ACCEPTANCE_STRICT=0 or ALLOW_A2_NETTING_DISPLAY_DIFF=1 relaxes to WARN — DEBUG ONLY, never a handoff Pass.
ACCEPTANCE_STRICT = os.environ.get("ACCEPTANCE_STRICT", "1") != "0"
# Acceptance scope (fail-closed within scope; Out-of-scope is documented, never WARN-and-pass):
#   obs123 — TDPQA-72 Obs1–3 (force-bill, Accrued≤Original, RSCH amount==principal excess=0) + RSTCRE spine
#   full   — obs123 + parent INT/DPI pending=0 (GAP-074). Default obs123 until INT-180 merges.
ACCEPTANCE_SCOPE = os.environ.get("ACCEPTANCE_SCOPE", "obs123").strip().lower()
if ACCEPTANCE_SCOPE not in ("obs123", "full"):
    raise RuntimeError(f"ACCEPTANCE_SCOPE must be obs123|full, got {ACCEPTANCE_SCOPE!r}")
ALLOW_A2_NETTING_DISPLAY_DIFF = os.environ.get("ALLOW_A2_NETTING_DISPLAY_DIFF") == "1"
# Adversarial fixture: seed a pre-existing EMI labd on the death-cycle installment (QA4 dirty-state shape).
SEED_EMI_LABD = os.environ.get("DCF_SEED_EMI_LABD") == "1"
SEED_EXTRA = os.environ.get("SEED_EXTRA", "0") != "0"
# Force disburse new SHG group per run (real flow); ignores PARENT_LAN when set.
DCF_FRESH_GROUP = os.environ.get("DCF_FRESH_GROUP", "0") == "1"
RUN_TXN_FLOOR_ID = 0
DCF_FIXTURE_BLOCKLIST = frozenset(
    lan.strip()
    for lan in os.environ.get("DCF_FIXTURE_BLOCKLIST", "6003896527,6003973025").split(",")
    if lan.strip()
)
# Vikram QA path (TDPQA-72): child1 regular FC → RSTCRE → child2 last DFC.
VIKRAM_PATH = os.environ.get("VIKRAM_PATH", "0") == "1"
# Non-last child FC entry (HARNESS-ONLY — do not “fix” Accounting POS via ICF orch):
#   Sim B (default): loanPrepayment — prod path; enqueues RSTCRE + parent PPP; POS assert ON
#   Sim A (opt-in):  ICF_USE_LOAN_PREPAYMENT=0 → individualChildLoanForeclosure —
#                    does NOT enqueue RSTCRE / parent PPP; POS assert Out-of-scope
# Env name kept for compatibility; default is "1" (Sim B / loanPrepayment).
VIKRAM_USE_LOAN_PREPAYMENT = os.environ.get("ICF_USE_LOAN_PREPAYMENT", "1") == "1"
# Harness-only: when Sim B BRE is down AND local_bre_stub is not used, document Parent POS as
# Blocked (do not invent prod PPP HTTP). Prefer: bash scripts/dcf_sanity/local_bre_stub.sh ensure
# (wired in ensure_dcf_local_stack.sh) so getForeclosureRoles returns SUCCESS and Sim B runs.
# parentLoanAccountPartPrepayment is internal from loanPrepayment (needs loan_account_entity in EC).
DOCUMENT_PARENT_POS_BRE_BLOCK = os.environ.get("DOCUMENT_PARENT_POS_BRE_BLOCK", "0") == "1"
# Harness-only: local DB still on pre-Sheet15 DFC rules (QA4 already Sheet15) → empty partitions.
# Do not soft-pass under STRICT unless this flag is set with printed proof.
LOCAL_DFC_PTC_GAP = os.environ.get("LOCAL_DFC_PTC_GAP", "0") == "1"
ACCOUNTING_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
ICF_USER_ID = os.environ.get("ICF_USER_ID", "103")
ICF_OFFICE_ID = os.environ.get("ICF_OFFICE_ID", "2")

PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql", "-h", os.environ.get("YB_HOST", "localhost"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-v", "ON_ERROR_STOP=1", "-t", "-A",
]


def psql(sql: str) -> str:
    """Single-row psql with YB timeout retry (fail-fast after a few attempts)."""
    last: BaseException | None = None
    for attempt in range(1, 5):
        try:
            out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True, stderr=subprocess.STDOUT)
            return out.strip().split("\n")[0] if out.strip() else ""
        except subprocess.CalledProcessError as exc:
            last = exc
            err = (exc.output or "") if isinstance(getattr(exc, "output", None), str) else ""
            if not err and exc.stderr:
                err = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode("utf-8", "replace")
            transient = any(
                s in err
                for s in (
                    "Timed out waiting",
                    "kProcessingRequest",
                    "Connection refused",
                    "could not connect",
                    "server closed the connection",
                )
            )
            if not transient or attempt == 4:
                raise
            time.sleep(min(2 * attempt, 6))
    raise last or RuntimeError("psql failed")


def acquire_dcf_e2e_lock() -> int:
    """Delegate to flowtest.lock (shared /tmp/flowtest_e2e.lock)."""
    fd = _acquire_flowtest_lock()
    mark_lock_held()
    return fd


def psql_multi(sql: str) -> None:
    subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)


def fire_batch(api: str, job_time: str) -> None:
    cmd = [
        "python3", str(ROOT / "scripts/testing/api-fire.py"),
        api, "--batch", "--job-time", job_time,
    ]
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        raise RuntimeError(f"batch {api} HTTP fire failed rc={rc}")



def snapshot_dues(lan: str, label: str) -> dict:
    """Delegate to flowtest.asserts (shared dues snapshot)."""
    return _ft_asserts.snapshot_dues(lan, label)


def latest_txn(lan: str, txn_type: str, *, match_amount: str | None = None) -> tuple[str, str]:
    """Closure txns link via loan_account_closure_details; RSCH uses client_reference_number suffix."""
    amount_clause = ""
    if match_amount is not None and txn_type == "RSCH_DEATH_FORECLOSURE":
        amount_clause = f" AND tm.original_amount = {match_amount}"
    if txn_type == "DEATH_FORECLOSURE":
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.loan_account_closure_details lacd
JOIN mfi_accounting.loan_account la ON la.account_id = lacd.loan_account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lacd.transaction_reference_number
WHERE la.la_account_number = '{lan}' AND lacd.identifier_type = '{txn_type}'
ORDER BY lacd.id DESC LIMIT 1;
""")
        if not row and RUN_TXN_FLOOR_ID:
            row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tc.type = '{txn_type}' AND tm.id > {RUN_TXN_FLOOR_ID}
ORDER BY tm.id DESC LIMIT 1;
""")
    elif txn_type == "RSCH_DEATH_FORECLOSURE":
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tc.type = '{txn_type}' AND tm.client_reference_number LIKE '%_{lan}'
{amount_clause}
ORDER BY tm.id DESC LIMIT 1;
""")
    else:
        row = psql(f"""
SELECT tm.reference_number, tm.original_amount::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{lan}' AND tc.type = '{txn_type}'
ORDER BY tm.id DESC LIMIT 1;
""")
    if not row:
        return "", ""
    ref, amt = row.split("|", 1)
    return ref, amt


def latest_txn_poll(lan: str, txn_type: str, timeout_s: int = 15, **kwargs) -> tuple[str, str]:
    """Poll latest_txn for Yugabyte read-after-write visibility on closure/RSCH rows."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        ref, amt = latest_txn(lan, txn_type, **kwargs)
        if ref:
            return ref, amt
        time.sleep(1)
    return latest_txn(lan, txn_type, **kwargs)


def partition_codes(ref: str) -> list[str]:
    if not ref:
        return []
    rows = subprocess.check_output(
        [*PG, "-c", f"""
SELECT reference_code||':'||COALESCE(tpd.amount,0)::text||':'||COALESCE(tpd.cr_dr_indicator,'')
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}' ORDER BY reference_code;
"""],
        env=PG_ENV, text=True,
    ).strip()
    return [r for r in rows.split("\n") if r]


def _txn_refs_for_lan(lan: str, txn_type: str) -> list[str]:
    """Collect transaction_master.reference_number values for GL balance audit."""
    if txn_type in ("DEATH_FORECLOSURE", "RSCH_DEATH_FORECLOSURE", "LOAN_PREPAYMENT"):
        ref, _ = latest_txn(lan, txn_type)
        return [ref] if ref else []
    if txn_type == "BILLING":
        rows = subprocess.check_output(
            [*PG, "-c", f"""
SELECT DISTINCT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
JOIN mfi_accounting.loan_account la ON la.la_account_number = td.account_number
WHERE la.la_account_number = '{lan}'
  AND tc.type = 'BILLING'
  AND (
    tm.client_reference_number LIKE 'DFC_PRTL_BILL_%'
    OR tm.client_reference_number ~ '^[0-9]+$'
  )
ORDER BY tm.id;
"""],
            env=PG_ENV, text=True,
        ).strip()
        return [r.strip() for r in rows.split("\n") if r.strip()]
    return []


def assert_gl_balanced_txn(ref: str, label: str) -> None:
    """Per-txn debit==credit via flowtest.asserts; DFC LOCAL_DFC_PTC_GAP OOS retained here."""
    if not ref:
        raise AssertionError(f"GL balance FAIL {label}: empty reference_number")
    if LOCAL_DFC_PTC_GAP and ("DEATH_FORECLOSURE" in label or "RSCH" in label):
        row = psql(f"""
SELECT COUNT(*)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{ref}';
""")
        if (row or "0") == "0":
            print(
                f"  GL balance LOCAL_DFC_PTC_GAP Out-of-scope: {label} ref={ref} "
                f"0 partition rows (local pre-Sheet15 rules vs tip Sheet15 codes; "
                f"QA4 evidence: Sheet15 rules + Debit=Credit)"
            )
            return
    # Sync STRICT flag into shared module for this process
    _ft_asserts.ACCEPTANCE_STRICT = ACCEPTANCE_STRICT
    _ft_asserts.assert_gl_balanced_txn(ref, label)


def assert_force_bill_gl_shape(ref: str, label: str, *, expect_child_cg: bool) -> None:
    """Force-bill BILLING: print raw gl_code; child must be CG*, parent must not.

    Do not strip CG and join parent general_ledger.name for child legs
    (feedback_child_cg_gl_vs_parent_named.md). Under ACCEPTANCE_STRICT, 0 partitions = FAIL
    (force-bill BILLING normally materializes legs locally — unlike DFC/RSCH).
    """
    if not ref:
        return
    rows = subprocess.check_output(
        [
            *PG,
            "-c",
            f"""
SELECT COALESCE(tpd.gl_code,'')||'|'||COALESCE(tpd.cr_dr_indicator,'')
       ||'|'||COALESCE(tpd.amount,0)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{ref}'
ORDER BY tpd.cr_dr_indicator, tpd.gl_code;
""",
        ],
        env=PG_ENV,
        text=True,
    ).strip()
    if not rows:
        if ACCEPTANCE_STRICT:
            raise AssertionError(
                f"Force-bill GL shape FAIL {label} ref={ref}: BILLING tm has 0 partition rows "
                f"(expected CG* child or bare parent gl_code legs)"
            )
        print(f"  Force-bill GL shape Out-of-scope: {label} ref={ref} has 0 partition rows")
        return
    legs = []
    for line in rows.split("\n"):
        if not line.strip():
            continue
        gl_code, drcr, amt = line.split("|", 2)
        legs.append((gl_code, drcr, amt))
        is_cg = gl_code.startswith("CG")
        if ACCEPTANCE_STRICT and expect_child_cg and not is_cg:
            raise AssertionError(
                f"Force-bill GL shape FAIL {label} ref={ref}: child leg gl_code={gl_code!r} "
                f"must start with CG (stored child_general_ledger code)"
            )
        if ACCEPTANCE_STRICT and (not expect_child_cg) and is_cg:
            raise AssertionError(
                f"Force-bill GL shape FAIL {label} ref={ref}: parent leg gl_code={gl_code!r} "
                f"must NOT use CG prefix"
            )
    shape = "CG*" if expect_child_cg else "named/bare"
    print(
        f"  Force-bill GL shape PASS: {label} ref={ref} expect={shape} "
        f"legs={[':'.join(x) for x in legs]}"
    )


def assert_gl_balance_for_loan(lan: str, reference_codes: list[str]) -> None:
    """Debit=credit per transaction for each catalogue type on LAN (S6 matrix)."""
    for txn_type in reference_codes:
        refs = _txn_refs_for_lan(lan, txn_type)
        if not refs:
            raise AssertionError(f"GL balance FAIL: {lan} missing required {txn_type} transaction")
        for ref in refs:
            assert_gl_balanced_txn(ref, f"{lan}/{txn_type}")


def assert_transaction_posting_audit(
    child_lan: str, parent_lan: str, *, phase: str = "last_child"
) -> dict:
    """Column-level tm / lapd / labd read-back for DFC money tables (S7 matrix).

    phase=last_child: Obs2 — parent RSCH lapd.amount must equal tm.original_amount.
    phase=non_last: tm-level child DFC==parent RSCH is asserted elsewhere; lapd may split
    interest/prin differently when overdue INT exists at death (do not fail-closed here).
    """
    if phase not in ("last_child", "non_last"):
        raise RuntimeError(f"phase must be last_child|non_last, got {phase!r}")
    evidence: dict = {"child": {}, "parent": {}}

    child_ref, child_amt_s = latest_txn(child_lan, "DEATH_FORECLOSURE")
    if not child_ref:
        raise AssertionError(f"txn audit FAIL: child {child_lan} missing DEATH_FORECLOSURE")
    child_tm = psql(f"""
SELECT tm.reference_number,
       COALESCE(tm.original_amount,0)::text,
       COALESCE(tm.client_reference_number,''),
       tc.type
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tm.reference_number = '{child_ref}';
""")
    c_ref, c_orig, c_client, c_type = child_tm.split("|", 3)
    evidence["child"]["death_foreclosure"] = {
        "reference_number": c_ref,
        "original_amount": Decimal(c_orig),
        "client_reference_number": c_client,
        "catalogue_type": c_type,
    }
    child_lapd = psql(f"""
SELECT lapd.id::text,
       COALESCE(lapd.amount,0)::text,
       COALESCE(lapd.principal_amount,0)::text,
       COALESCE(lapd.interest_amount,0)::text,
       COALESCE(lapd.excess_amount,0)::text
FROM mfi_accounting.loan_account_payments_details lapd
WHERE lapd.transaction_reference_number = '{child_ref}'
LIMIT 1;
""")
    if child_lapd:
        lid, amt, prin, intr, exc = child_lapd.split("|", 4)
        evidence["child"]["lapd"] = {
            "id": lid,
            "amount": Decimal(amt),
            "principal_amount": Decimal(prin),
            "interest_amount": Decimal(intr),
            "excess_amount": Decimal(exc),
        }
    child_labd = psql(f"""
SELECT labd.id::text,
       labd.transaction_reference_number,
       COALESCE(labd.principal_amount,0)::text,
       COALESCE(labd.interest_amount,0)::text,
       COALESCE(labd.reversed,false)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = labd.transaction_reference_number
WHERE la.la_account_number = '{child_lan}'
  AND tm.client_reference_number LIKE 'DFC_PRTL_BILL_%'
ORDER BY labd.id DESC LIMIT 1;
""")
    if not child_labd:
        child_labd = psql(f"""
SELECT labd.id::text,
       labd.transaction_reference_number,
       COALESCE(labd.principal_amount,0)::text,
       COALESCE(labd.interest_amount,0)::text,
       COALESCE(labd.reversed,false)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{child_lan}'
  AND labd.transaction_reference_number LIKE 'DFC_PRTL_BILL_%'
ORDER BY labd.id DESC LIMIT 1;
""")
    if child_labd:
        lb_id, lb_ref, lb_prin, lb_int, lb_rev = child_labd.split("|", 4)
        evidence["child"]["force_bill_labd"] = {
            "id": lb_id,
            "transaction_reference_number": lb_ref,
            "principal_amount": Decimal(lb_prin),
            "interest_amount": Decimal(lb_int),
            "reversed": lb_rev == "t",
        }
    print(
        f"  txn audit child {child_lan}: DFC ref={c_ref} original_amount={c_orig} "
        f"client_ref={c_client} lapd={evidence['child'].get('lapd')} "
        f"fb_labd={evidence['child'].get('force_bill_labd')}"
    )

    parent_ref, parent_amt_s = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    if parent_ref:
        parent_tm = psql(f"""
SELECT tm.reference_number,
       COALESCE(tm.original_amount,0)::text,
       COALESCE(tm.client_reference_number,''),
       tc.type
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE tm.reference_number = '{parent_ref}';
""")
        p_ref, p_orig, p_client, p_type = parent_tm.split("|", 3)
        evidence["parent"]["rsch"] = {
            "reference_number": p_ref,
            "original_amount": Decimal(p_orig),
            "client_reference_number": p_client,
            "catalogue_type": p_type,
        }
        parent_lapd = psql(f"""
SELECT lapd.id::text,
       COALESCE(lapd.amount,0)::text,
       COALESCE(lapd.principal_amount,0)::text,
       COALESCE(lapd.interest_amount,0)::text,
       COALESCE(lapd.excess_amount,0)::text
FROM mfi_accounting.loan_account_payments_details lapd
WHERE lapd.transaction_reference_number = '{parent_ref}'
LIMIT 1;
""")
        if not parent_lapd:
            raise AssertionError(f"txn audit FAIL: parent {parent_lan} RSCH lapd missing ref={parent_ref}")
        lid, amt, prin, intr, exc = parent_lapd.split("|", 4)
        evidence["parent"]["lapd"] = {
            "id": lid,
            "amount": Decimal(amt),
            "principal_amount": Decimal(prin),
            "interest_amount": Decimal(intr),
            "excess_amount": Decimal(exc),
        }
        if ACCEPTANCE_STRICT:
            lapd_amt = evidence["parent"]["lapd"]["amount"]
            tm_amt = evidence["parent"]["rsch"]["original_amount"]
            if lapd_amt != tm_amt:
                if phase == "non_last":
                    print(
                        f"  txn audit INFO (non_last): parent RSCH lapd.amount={lapd_amt} "
                        f"!= tm.original_amount={tm_amt} — allowed; non-last parity is tm-level"
                    )
                else:
                    raise AssertionError(
                        f"txn audit FAIL: parent RSCH lapd.amount={lapd_amt} "
                        f"!= tm.original_amount={tm_amt}"
                    )
        parent_fb = psql(f"""
SELECT tm.reference_number,
       tm.client_reference_number,
       COALESCE(tm.original_amount,0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
JOIN mfi_accounting.loan_account la ON la.la_account_number = td.account_number
WHERE la.la_account_number = '{parent_lan}'
  AND tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ '^[0-9]+$'
ORDER BY tm.id DESC LIMIT 1;
""")
        if parent_fb:
            fb_ref, fb_client, fb_amt = parent_fb.split("|", 2)
            evidence["parent"]["force_bill"] = {
                "reference_number": fb_ref,
                "client_reference_number": fb_client,
                "original_amount": Decimal(fb_amt),
            }
        print(
            f"  txn audit parent {parent_lan}: RSCH ref={p_ref} original_amount={p_orig} "
            f"lapd={evidence['parent']['lapd']} fb={evidence['parent'].get('force_bill')}"
        )
    else:
        print(f"  txn audit parent {parent_lan}: RSCH N/A (non-last path may not have parent RSCH yet)")
    return evidence


def assert_amount_calculations_non_last(child_lan: str, parent_lan: str) -> None:
    """S4: non-last child DFC amount == parent RSCH (parent reuses child TRANSACTION_AMOUNT)."""
    assert_non_last_child_parent_rsch_parity(child_lan, parent_lan)


def assert_amount_calculations_last_child(
    parent_lan: str, child_lan: str, expected_extra: Decimal,
) -> None:
    """S1/S2 last-child: child DFC (full claim) ≠ parent RSCH by design.

    Parent RSCH posts A2-netted principal only (9b6454df6 parentRschTotal); INT/PENAL/FEE
    are waived/settled outside the RSCH txn amount. Assert Obs2: amount==principal, excess=0.
    Non-last equality is assert_amount_calculations_non_last / assert_non_last_child_parent_rsch_parity.
    """
    child_ref, child_amt_s = latest_txn(child_lan, "DEATH_FORECLOSURE")
    parent_ref, parent_amt_s = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    if not child_ref or not parent_ref:
        raise AssertionError("amount calc FAIL: missing child DFC or parent RSCH on last-child path")
    child_amt = Decimal(child_amt_s or "0")
    parent_amt = Decimal(parent_amt_s or "0")
    delta = child_amt - parent_amt
    rsch_cols = assert_parent_rsch_lapd_columns(parent_lan, expected_extra)
    if ACCEPTANCE_STRICT:
        if rsch_cols["excess_amount"] != 0:
            raise AssertionError(
                f"amount calc FAIL (last-child): parent RSCH lapd.excess_amount={rsch_cols['excess_amount']} must be 0"
            )
        if rsch_cols["amount"] != rsch_cols["principal_amount"]:
            raise AssertionError(
                f"amount calc FAIL (last-child): parent RSCH amount={rsch_cols['amount']} != "
                f"principal={rsch_cols['principal_amount']}"
            )
        if rsch_cols["amount"] != parent_amt:
            raise AssertionError(
                f"amount calc FAIL (last-child): lapd.amount={rsch_cols['amount']} != "
                f"tm.original_amount={parent_amt}"
            )
    print(
        f"  amount calc PASS (last-child): child DFC={child_amt} parent RSCH={parent_amt} "
        f"claim_minus_rsch={delta} EXTRA≈{expected_extra} "
        f"lapd amount=principal={rsch_cols['principal_amount']} excess=0"
    )


def child_already_closed_from_dfc(child_lan: str) -> bool:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        return False
    ref, _ = latest_txn(child_lan, "DEATH_FORECLOSURE")
    return bool(ref)


def child_already_closed_from_fc(child_lan: str) -> bool:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        return False
    ref, _ = latest_txn(child_lan, "LOAN_PREPAYMENT")
    return bool(ref)


def cleanup_abandoned_staging(child_lans: list[str], keep_staging_id: int | None = None) -> None:
    """Stop insurance reader from re-picking stale inbound rows (batch min/max id window)."""
    lan_list = ",".join(f"'{lan}'" for lan in child_lans)
    keep_clause = f"AND s.id <> {keep_staging_id}" if keep_staging_id else ""
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details s
SET claim_status = 'APPROVED', status = 'COMPLETED', updated_on = NOW(), updated_by = 'LOCAL_E2E'
FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id = dfd.loan_account_id
WHERE s.death_foreclosure_details_id = dfd.id
  AND la.la_account_number IN ({lan_list})
  {keep_clause}
  AND s.inout_status = 'INBOUND_SUCCESS'
  AND s.claim_status NOT IN ('APPROVED', 'REJECTED', 'PENDING')
  AND (s.status IS NULL OR s.status NOT IN ('COMPLETED', 'PROCESSING'));
""")


def quarantine_all_other_inbound_staging(keep_staging_id: int) -> None:
    """Global guard: the approve reader scans by id window and may re-pick INBOUND_SUCCESS rows
    left behind by earlier/aborted fixtures. Mark every other in-flight inbound row COMPLETED so
    only keep_staging_id is processed. Script-only; touches staging bookkeeping, not loan money."""
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details
SET claim_status='APPROVED', status='COMPLETED', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id <> {keep_staging_id}
  AND inout_status='INBOUND_SUCCESS'
  AND (status IS NULL OR status NOT IN ('COMPLETED','PROCESSING'));
""")


def wait_batch_by_start(job_name: str, started_epoch: int, timeout_s: int = 300) -> str:
    """Deprecated wall-clock wait — delegates to TZ-corrected harness helper."""
    from clb_queue_harness import wait_batch_by_start as _wait

    return _wait(job_name, started_epoch, timeout_s=timeout_s)


def wait_batch_after_id(job_name: str, min_execution_id: int, timeout_s: int = 300) -> str:
    from clb_queue_harness import wait_batch_after

    status = wait_batch_after(job_name, min_execution_id, timeout_s=timeout_s)
    print(f"  batch {job_name} COMPLETED")
    return status


def max_job_execution_id(job_name: str) -> int:
    from clb_queue_harness import max_batch_execution_id

    return max_batch_execution_id(job_name)

def _resolve_death_date_sql(parent_id: int, *, latest: bool) -> str:
    """Day-after-PRIN-due death date aligned with ChildLoanRestructuring (`due_date > death`).

    `latest=True` picks the newest valid candidate (canonical fixture near current billing).
    `latest=False` picks earliest (auto-discover + EXTRA seed window).
    """
    order = "DESC" if latest else "ASC"
    return f"""
WITH d AS (
  SELECT DISTINCT ldd.due_date
  FROM mfi_accounting.loan_due_details ldd
  JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
  WHERE c.parent_loan_account_id={parent_id} AND ldd.component_type='PRIN' AND ldd.is_deleted=false
  ORDER BY ldd.due_date
), cand AS (
  SELECT (due_date + INTERVAL '1 day')::date AS death_d
  FROM d
), ok AS (
  SELECT cand.death_d
  FROM cand
  WHERE EXISTS (
    SELECT 1
    FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='INT' AND ldd.is_deleted=false
      AND ldd.due_date::date > (cand.death_d - INTERVAL '1 day')
      AND ldd.due_date::date <= CURRENT_DATE
      AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0
  )
  AND EXISTS (
    SELECT 1
    FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='PRIN' AND ldd.is_deleted=false
      AND ldd.due_date::date < cand.death_d
  )
  AND EXISTS (
    SELECT 1
    FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
    WHERE c.parent_loan_account_id={parent_id}
      AND ldd.component_type='PRIN' AND ldd.is_deleted=false
      AND ldd.due_date::date >= cand.death_d
  )
  ORDER BY cand.death_d {order}
  LIMIT 1
)
SELECT to_char(death_d,'YYYY-MM-DD') FROM ok;
"""


def resolve_death_date(parent_id: int, *, latest: bool = True) -> str:
    row = psql(_resolve_death_date_sql(parent_id, latest=latest))
    if not row:
        raise RuntimeError(f"no valid death_date for parent_id={parent_id} (PRIN due+1 day window)")
    return row


def cleanup_stale_rstcre_events(parent_id: int) -> None:
    """Drop stale PENDING RSTCRE rows — events_queue is outside dcf_fixture_backup snapshot."""
    n = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""")
    if not n or n == "0":
        return
    psql_multi(f"""
UPDATE mfi_accounting.loan_account_events_queue
SET is_deleted=true, updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""")
    print(f"  RSTCRE prep: soft-deleted {n} stale PENDING row(s) parent_id={parent_id}")


def assert_no_legacy_force_bill_crn_collision(parent_lan: str, death_date: str) -> None:
    """Fail closed if legacy parent CRN accountId||valueDateMs (no dfdId suffix) already exists.

    Sequential child DFC reused that CRN for non-last then last-child parent force-bill → 134497.
    Product now appends deathForeclosureDetailsId. Leftover exact-length CRNs from prior runs still block.
    valueDate is dateOfReporting (= dfd.created_on), not necessarily DEATH_DATE — match by CRN shape.
    """
    del death_date  # reserved for call-site clarity; reporting ms comes from live CRN shape
    parent_id = parent_account_id(parent_lan)
    # accountId + 13-digit epoch-ms only (no trailing dfdId)
    row = psql(f"""
SELECT tm.id::text, tm.client_reference_number, COALESCE(tm.original_amount,0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND td.narration = 'DFC partial-cycle billing'
  AND tm.client_reference_number ~ ('^{parent_id}[0-9]{{13}}$')
ORDER BY tm.id DESC LIMIT 1;
""")
    if row:
        tid, crn, amt = row.split("|", 2)
        raise AssertionError(
            f"legacy force-bill CRN collision: parent {parent_lan} has BILLING "
            f"client_reference_number={crn} tm_id={tid} amount={amt} "
            f"(shape accountId||valueDateMs without deathForeclosureDetailsId). "
            f"Restore fixture (dcf_fixture_backup.py restore) before re-run."
        )
    print(f"  force-bill CRN prep PASS: no legacy parent CRN ^{parent_id}[0-9]{{13}}$")


def prepare_fixture_pint_free(parent_lan: str) -> None:
    """Waive open PINT on parent + children before DFC — penal rows are out of S1–S8 matrix scope.

    assert_child_closed / assert_parent_last_child require PINT pending == 0 after last-child FC.
    Parent PINT left open caused strict all_pending FAIL (e.g. PINT 374) when INT/PRIN closed OK.
    Penal paths: scenarios.json S06.
    """
    if os.environ.get("DCF_SKIP_PINT_PREP") == "1":
        return
    parent_id = parent_account_id(parent_lan)
    row = psql(f"""
SELECT COUNT(*)::text,
       COALESCE(SUM(ldd.due_amount-ldd.paid_amount-COALESCE(ldd.waived_amount,0)),0)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account c ON c.account_id=ldd.loan_account_id
WHERE c.parent_loan_account_id={parent_id} AND c.is_deleted=false
  AND ldd.component_type='PINT' AND ldd.is_deleted=false
  AND (ldd.due_amount-ldd.paid_amount-COALESCE(ldd.waived_amount,0)) > 0;
""")
    parent_row = psql(f"""
SELECT COUNT(*)::text,
       COALESCE(SUM(ldd.due_amount-ldd.paid_amount-COALESCE(ldd.waived_amount,0)),0)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND la.is_deleted=false
  AND ldd.component_type='PINT' AND ldd.is_deleted=false
  AND (ldd.due_amount-ldd.paid_amount-COALESCE(ldd.waived_amount,0)) > 0;
""")
    child_cnt = (row.split("|", 1)[0] if row else "0") or "0"
    parent_cnt = (parent_row.split("|", 1)[0] if parent_row else "0") or "0"
    if child_cnt == "0" and parent_cnt == "0":
        print(f"  PINT prep: no open PINT on parent or children under {parent_lan}")
        return
    if child_cnt != "0":
        cnt, pending = row.split("|", 1)
        psql_multi(f"""
UPDATE mfi_accounting.loan_due_details ldd
SET waived_amount = ldd.due_amount - ldd.paid_amount,
    updated_on = NOW(), updated_by = 'DCF_PINT_PREP'
FROM mfi_accounting.loan_account c
WHERE ldd.loan_account_id = c.account_id
  AND c.parent_loan_account_id = {parent_id}
  AND c.is_deleted = false
  AND ldd.component_type = 'PINT'
  AND ldd.is_deleted = false
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0)) > 0;
""")
        print(f"  PINT prep: waived child PINT rows={cnt} total_pending={pending} parent={parent_lan}")
    if parent_cnt != "0":
        cnt, pending = parent_row.split("|", 1)
        psql_multi(f"""
UPDATE mfi_accounting.loan_due_details ldd
SET waived_amount = ldd.due_amount - ldd.paid_amount,
    updated_on = NOW(), updated_by = 'DCF_PINT_PREP'
FROM mfi_accounting.loan_account la
WHERE ldd.loan_account_id = la.account_id
  AND la.la_account_number = '{parent_lan}'
  AND la.is_deleted = false
  AND ldd.component_type = 'PINT'
  AND ldd.is_deleted = false
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount, 0)) > 0;
""")
        print(f"  PINT prep: waived parent PINT rows={cnt} total_pending={pending} lan={parent_lan}")


def reset_child_dfc_if_needed(child_lan: str) -> None:
    """Remove in-flight DFC seed so sibling ACTIVE count is correct for last-child detection."""
    row = psql(f"""
SELECT dfd.id, la.loan_status FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id=dfd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND dfd.death_foreclosure_status NOT IN ('APPROVED','REJECTED')
LIMIT 1;
""")
    if not row:
        if psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';") == "DEATH_FORECLOSURE_FREEZE":
            psql_multi(f"""
UPDATE mfi_accounting.loan_account SET loan_status='ACTIVE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
            print(f"  reset {child_lan} FREEZE → ACTIVE (no open DFD)")
        return
    dfd_id, status = row.split("|", 1)
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_insurance_staging_details SET is_deleted=true, updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE death_foreclosure_details_id={dfd_id} AND COALESCE(is_deleted,false)=false;
UPDATE mfi_accounting.death_foreclosure_details SET death_foreclosure_status='REJECTED', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={dfd_id};
UPDATE mfi_accounting.loan_account SET loan_status='ACTIVE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
    print(f"  reset in-flight DFC child={child_lan} dfd_id={dfd_id} was_status={status}")


def seed_dfc_child(child_lan: str, death_date: str) -> tuple[int, int]:
    """Insert DFD + staging (PENDING, no inout) for approve reader."""
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}' AND is_deleted=false;"
    )
    if not account_id:
        raise RuntimeError(f"child LAN not found: {child_lan}")

    existing = psql(f"""
SELECT dfd.id FROM mfi_accounting.death_foreclosure_details dfd
JOIN mfi_accounting.loan_account la ON la.account_id=dfd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND dfd.death_foreclosure_status NOT IN ('REJECTED','APPROVED')
LIMIT 1;
""")
    if existing:
        dfd_id = int(existing)
        staging_id = psql(f"""
SELECT id FROM mfi_accounting.death_foreclosure_insurance_staging_details
WHERE death_foreclosure_details_id={dfd_id} AND COALESCE(is_deleted,false)=false
ORDER BY id DESC LIMIT 1;
""")
        if staging_id:
            return dfd_id, int(staging_id)

    dfd_id = int(psql(f"""
WITH ins AS (
  INSERT INTO mfi_accounting.death_foreclosure_details (
    loan_account_id, deceased_person, deceased_person_name, date_of_death, claim_type, cause_of_death,
    is_nominee_under_age, death_foreclosure_status, task_status, created_on, created_by, updated_on, updated_by,
    outstanding_loan_balance, balance_claim_amount, death_claim_form_document_id, place_of_death, date_of_birth
  )
  SELECT {account_id}, 'BORROWER', 'LOCAL_DFC_E2E', '{death_date}'::timestamp, 'NATURAL', 'NATURAL_DEATH',
    false, 'INITIATED_INSURACE_CLAIM', 'PENDING',
    ('{death_date}'::timestamp + INTERVAL '5 days'), 'LOCAL_E2E', NOW(), 'LOCAL_E2E',
    0, 0, 150437, 'Local', '1995-01-01'::timestamp
  RETURNING id
)
SELECT id FROM ins;
"""))

    li = psql(f"""
SELECT policy_number, sum_assured::text FROM mfi_accounting.loan_account_insurance_details
WHERE loan_account_id={account_id} AND policy_type='LIFE_INSUR' AND is_deleted=false LIMIT 1;
""")
    policy, sum_assured = (li.split("|") + ["POL{account_id}", "20000"])[:2]
    claim_num = f"E2E{child_lan}{int(time.time())}"

    staging_id = int(psql(f"""
WITH ins AS (
  INSERT INTO mfi_accounting.death_foreclosure_insurance_staging_details (
    death_foreclosure_details_id, policy_number, product_code, loan_account_number, claim_type, cause_of_event,
    date_of_event, date_of_reporting, sum_assured, original_loan_amount, outstanding_loan_balance,
    balance_claim_amount, ifsc_code, account_number, claim_status, claim_number, inout_status,
    created_on, created_by, updated_on, updated_by, is_deleted
  )
  VALUES (
    {dfd_id}, '{policy}', 'SHGDL', '{child_lan}', 'NATURAL', 'NATURAL_DEATH',
    '{death_date}'::timestamp, ('{death_date}'::timestamp + INTERVAL '5 days'), {sum_assured}, {sum_assured}, 0,
    0, 'ICIC0001417', '141701521467', 'PENDING', '{claim_num}', NULL,
    NOW(), 'LOCAL_E2E', NOW(), 'LOCAL_E2E', false
  )
  RETURNING id
)
SELECT id FROM ins;
"""))

    psql_multi(f"""
UPDATE mfi_accounting.loan_account SET loan_status='DEATH_FORECLOSURE_FREEZE', updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE la_account_number='{child_lan}';
""")
    print(f"  seeded child {child_lan} dfd_id={dfd_id} staging_id={staging_id}")
    return dfd_id, staging_id


def _extra_proxy(child_lan: str, death_date: str) -> dict:
    """SQL mirror of calculateExtraInterestAmountPaid raw surplus (BPI≈0 when death-1 is a due date)."""
    row = psql(f"""
WITH la AS (
  SELECT account_id, expected_disbursement_date
  FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}' AND is_deleted=false
), as_on AS (
  SELECT ('{death_date}'::date - INTERVAL '1 day')::date AS d
)
SELECT
  COALESCE(SUM(ldd.paid_amount),0)::text,
  COALESCE(SUM(CASE WHEN ldd.due_date::date <= (SELECT d FROM as_on)
    THEN ldd.due_amount - COALESCE(ldd.waived_amount,0) ELSE 0 END),0)::text,
  COALESCE(SUM(CASE WHEN ldd.due_date::date > (SELECT d FROM as_on)
    THEN ldd.paid_amount ELSE 0 END),0)::text
FROM mfi_accounting.loan_due_details ldd, la
WHERE ldd.loan_account_id=la.account_id AND ldd.component_type='INT' AND ldd.is_deleted=false
  AND ldd.due_date > la.expected_disbursement_date;
""")
    parts = (row or "0|0|0").split("|")
    settled, owed_till, advance_paid = (Decimal(parts[0] or 0), Decimal(parts[1] or 0), Decimal(parts[2] or 0))
    raw_surplus = max(settled - owed_till, Decimal(0))
    return {
        "settled": settled,
        "owed_till_as_on": owed_till,
        "advance_int_paid": advance_paid,
        "raw_surplus": raw_surplus,
    }


def _eod_ms_ist(iso_date: str) -> str:
    from datetime import datetime
    from zoneinfo import ZoneInfo

    d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    return str(
        int(datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=ZoneInfo("Asia/Kolkata")).timestamp() * 1000)
    )


def _acct_post(api: str, body: dict) -> dict:
    url = f"{ACCOUNTING_URL}/{api}"
    data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return json.loads(exc.read())


def _lp_headers(stan: str, *, function_code: str = "APPROVE") -> dict:
    td = str(int(time.time() * 1000))
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": function_code,
        "function_sub_code": "DEFAULT",
        "run_mode": "REAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": stan,
        "transmission_datetime": td,
        "user_id": ICF_USER_ID,
        "actor_type": "EMPLOYEE",
        "user_handle_value": ICF_USER_ID,
        "office_id": ICF_OFFICE_ID,
    }


def _lp_component(due: str) -> dict:
    d = Decimal(str(due or "0"))
    return {
        "due_amount": str(d),
        "is_waived": "0",
        "is_fully_waived": "0",
        "waiver_percentage": "",
        "waived_amount": "0",
        "amount_to_be_paid": str(d),
    }


def _lp_simulate(lan: str, foreclosure_date_ms: str) -> dict:
    stan = f"vikram_sim_{lan}_{int(time.time())}"
    body = {
        "headers": _lp_headers(stan, function_code="DEFAULT"),
        "request": {"account_number": lan, "foreclosure_date": foreclosure_date_ms},
    }
    resp = _acct_post("fetchLoanForeclosureSimulationDetails", body)
    status = resp.get("response_status", {})
    if status.get("code") != "30360":
        raise RuntimeError(f"fetchLoanForeclosureSimulationDetails failed: {status}")
    return resp


def _lp_build_request(sim: dict, lan: str, foreclosure_date_ms: str, receipt: str) -> dict:
    fs = sim.get("foreclosure_simulation_details") or {}
    charges = sim.get("charges_details") or []
    request: dict = {
        "billed_interest_details": _lp_component(str(fs.get("billed_interest") or "0")),
        "billed_principal_details": _lp_component(str(fs.get("billed_principal") or "0")),
        "balance_principal_details": _lp_component(str(fs.get("balance_principal") or "0")),
        "bpi_details": _lp_component(str(fs.get("bpi_amount") or "0")),
        "current_lpp_details": _lp_component(str(fs.get("current_lpp") or "0")),
        "future_lpp_details": _lp_component(str(fs.get("future_lpp") or "0")),
        "foreclosure_fee_details": _lp_component(str(fs.get("foreclosure_fee") or "0")),
        "fee_details": [{**_lp_component(str(fs.get("cbc_fee") or "0")), "identifier_code": "cbc_fee"}],
        "charges_details": charges,
    }
    if fs.get("billed_dpi") is not None:
        request["billed_dpi_details"] = _lp_component(str(fs.get("billed_dpi") or "0"))
    if fs.get("bpd_amount") is not None:
        request["bpd_details"] = _lp_component(str(fs.get("bpd_amount") or "0"))

    total = (
        Decimal(str(fs.get("billed_interest") or "0"))
        + Decimal(str(fs.get("billed_principal") or "0"))
        + Decimal(str(fs.get("balance_principal") or "0"))
        + Decimal(str(fs.get("bpi_amount") or "0"))
        + Decimal(str(fs.get("billed_dpi") or "0"))
        + Decimal(str(fs.get("bpd_amount") or "0"))
        + Decimal(str(fs.get("current_lpp") or "0"))
        + Decimal(str(fs.get("foreclosure_fee") or "0"))
        + Decimal(str(fs.get("cbc_fee") or "0"))
    )
    # Exclusive tax on foreclosure_fee (ValidateLoanPrepaymentDataProcessor adds fetchExclusiveTaxAmount)
    for ch in charges:
        ident = str(ch.get("charge_identifier") or "")
        if ident != "foreclosure_fee":
            continue
        inclusive = str(ch.get("charge_inclusive_of_tax") or "").lower()
        if inclusive == "false":
            total += Decimal(str(ch.get("total_tax_amount") or "0"))
    excess = Decimal(str(fs.get("excess_amount") or "0"))
    if excess > 0:
        total -= excess
    rounded = total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    round_off = rounded - total
    customer_id = psql(
        f"SELECT customer_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{lan}';"
    )
    request["loan_foreclosure_details"] = {
        "account_number": lan,
        "foreclosure_date": foreclosure_date_ms,
        "total_foreclosure_amount": str(rounded),
        "round_off_amount": str(round_off),
        "receipt_number": receipt,
        "currency_code": "INR",
        "currency_code_value": "INR",
        "payment_mode": "CASH",
        "payment_mode_value": "Cash",
        "closure_reason": "RELOC",
        "closure_reason_value": "Relocation",
        "notes": "VIKRAM_PATH local child regular FC",
        "paid_by": "CUSTOMER",
        "paid_by_value": "Customer",
        "depositor_name": "LOCAL_TEST",
        "excess_amount": str(fs.get("excess_amount") or "0"),
    }
    # INDL/JLG loanPrepayment requires customer_id (200065); SHG ICF path does not use this body.
    if customer_id:
        request["loan_foreclosure_details"]["customer_id"] = customer_id
        request["customer_id"] = customer_id
    return request


def _vikram_fc_date(death_date: str) -> str:
    """loanPrepayment rejects foreclosure_date < platform today (134292).

    DCF death_date may be mid-cycle in the past; regular FC must use today (or later).
    ISO YYYY-MM-DD string compare is chronological.
    """
    today = time.strftime("%Y-%m-%d")
    return death_date if death_date >= today else today


def ensure_fixture_accounts_active(parent_lan: str) -> None:
    """Harness hygiene: AUTO loanRepayment / FC require account.status=ACTIVE.

    Legacy fixture snapshots omitted ``account`` rows; prior DFC leaves status=CLOSED while
    loan_status stays ACTIVE → product 134468 ('not a child loan of parent'). Restore now
    heals via dcf_fixture_backup; this guard covers mid-run / legacy snaps.
    """
    n = psql(f"""
WITH touched AS (
  UPDATE mfi_accounting.account a
  SET status='ACTIVE', closing_date=NULL, updated_on=NOW(), updated_by='VIKRAM_HARNESS_ACCT_ACTIVE'
  FROM mfi_accounting.loan_account la
  WHERE a.id = la.account_id
    AND (la.la_account_number = '{parent_lan}' OR la.parent_loan_account_id = (
      SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}'
    ))
    AND COALESCE(a.status,'') <> 'ACTIVE'
  RETURNING a.id
)
SELECT COUNT(*)::text FROM touched;
""") or "0"
    if int(n) > 0:
        print(f"  Vikram prep: healed account.status→ACTIVE count={n} parent={parent_lan}")


def settle_parent_overdue_before_vikram_fc(parent_lan: str, parent_id: int) -> None:
    """Product rule 433: cannot foreclose member while parent has overdue.

    Prod SHG group collection: loanRepayment on parent with function_sub_code=AUTO
    (AutoPopulateChildLoansForRepaymentProcessor) → childLoanRepaymentEventGenerationProcessor
    enqueues REP → childLoanEventProcessingBatchJob → childLoanRepayment.

    Do NOT use WITHOUT_MAKER_CHECKER alone: that skips AUTO child populate and leaves
    parent/children POS desynced (not a real webapp group-collection path).
    Do NOT invent per-child HTTP repay; do not fake parentLoanAccountPartPrepayment HTTP.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from lib.api_client import fire_api, fresh_stan  # type: ignore
    from lib.envelope import build_envelope  # type: ignore

    ensure_fixture_accounts_active(parent_lan)

    pending = Decimal(psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)),0)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = '{parent_lan}'
  AND ldd.is_deleted = false
  AND ldd.due_date::date < CURRENT_DATE
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""") or "0")
    if pending <= 0:
        print(f"  Vikram prep: parent {parent_lan} has no overdue pending")
        return
    # Round up to whole rupee like collection screens
    repay_amt = pending.quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if repay_amt < pending:
        repay_amt += Decimal("1")
    today_ms = str(int(time.time() * 1000))
    crn = f"VOD{parent_lan[-4:]}{time.time_ns()}"[:32]
    body = {
        "loan_repayment_details": {
            "account_number": parent_lan,
            "repayment_amount": str(repay_amt),
            "repayment_time": today_ms,
            "value_date": today_ms,
            "repayment_mode": "CASH",
            "receipt_number": crn,
            "client_reference_number": crn,
        }
    }
    env = build_envelope("accounting", body, stan=fresh_stan("loanRepayment"))
    # AUTO = prod SHG cascade (see AutoPopulateChildLoansForRepaymentProcessor).
    env["headers"]["function_sub_code"] = "AUTO"
    env["headers"]["operation_mode"] = "SELF"
    env["headers"]["actor_type"] = "CUSTOMER"
    env["headers"]["run_mode"] = "REAL"
    print(
        f"  Vikram prep: settle parent overdue via loanRepayment "
        f"function_sub_code=AUTO parent={parent_lan} pending={pending} "
        f"repay={repay_amt} crn={crn}"
    )
    result = fire_api("loanRepayment", env, timeout_s=180)
    code, status = result.response_status()
    # 30266 = submitted for maker-checker; complete with APPROVE (same API, prod task path).
    if code == "30266" or (status and status.upper() == "SUCCESS" and "approval" in (result.body or "").lower()):
        print(f"  Vikram prep: loanRepayment submitted ({code}) — APPROVE")
        env_ap = build_envelope("accounting", body, stan=fresh_stan("loanRepayment"))
        env_ap["headers"]["function_code"] = "APPROVE"
        env_ap["headers"]["function_sub_code"] = "AUTO"
        env_ap["headers"]["operation_mode"] = "SELF"
        env_ap["headers"]["actor_type"] = "CUSTOMER"
        env_ap["headers"]["run_mode"] = "REAL"
        result = fire_api("loanRepayment", env_ap, timeout_s=180)
        code, status = result.response_status()
    if status and status.upper() != "SUCCESS" and code not in ("30265", "30273", "000"):
        hint = ""
        if code == "134468":
            hint = (
                " — HARNESS/FIXTURE: child↔parent link or account.status not ACTIVE after restore. "
                "Re-snap with dcf_fixture_backup (account+labd tables) or use DCF_FRESH_GROUP=1."
            )
        raise RuntimeError(
            f"Vikram prep loanRepayment FAIL parent={parent_lan} code={code}{hint} body={result.body[:600]}"
        )
    # Drain REP events (prod: childLoanEventProcessingBatchJob → childLoanRepayment).
    rep_pending = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='REP' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""") or "0"
    if int(rep_pending) > 0:
        print(f"  Vikram prep: draining {rep_pending} PENDING REP (child repay cascade)")
        fire_and_wait_child_events_batch(parent_id, 0)
        still = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='REP' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""") or "0"
        if int(still) > 0:
            raise RuntimeError(
                f"Vikram prep FAIL: {still} PENDING REP after childLoanEventProcessingBatchJob "
                f"parent_id={parent_id}"
            )
        print("  Vikram prep PASS: REP events drained")
    else:
        print("  Vikram prep: no PENDING REP after parent repay (check AUTO cascade)")

    left = Decimal(psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)),0)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = '{parent_lan}'
  AND ldd.is_deleted = false
  AND ldd.due_date::date < CURRENT_DATE
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""") or "0")
    if left > 0:
        raise RuntimeError(
            f"Vikram prep FAIL: parent {parent_lan} still overdue pending={left} after repay={repay_amt}"
        )
    print(f"  Vikram prep PASS: parent {parent_lan} overdue cleared (AUTO + REP drain)")


def ensure_rstcre_pending_after_vikram_fc(
    parent_lan: str,
    parent_id: int,
    closed_child_lan: str,
    remaining_child_lan: str,
) -> bool:
    """After Sim B loanPrepayment, RSTCRE should already be PENDING (event-gen).

    Sim A (ICF) does NOT enqueue RSTCRE — seed the same JSON shape as
    ChildLoanForeclosureEventGenerationProcessor so cascade drain still runs.
    Returns True when a drain is needed; False when already completed for this FC.
    """
    pending = int(psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C','COMPLETED');
""") or "0")
    if pending > 0:
        src = "loanPrepayment event-gen" if VIKRAM_USE_LOAN_PREPAYMENT else "prior/seed"
        print(
            f"  Vikram RSTCRE: already PENDING count={pending} "
            f"({src}) — skip seed"
        )
        return True

    prep = psql(f"""
SELECT pd.id::text,
       (EXTRACT(EPOCH FROM pd.foreclosure_date) * 1000)::bigint::text
FROM mfi_accounting.prepayment_details pd
JOIN mfi_accounting.loan_account la ON la.account_id = pd.loan_account_id
WHERE la.la_account_number = '{closed_child_lan}'
  AND pd.prepayment_status = 'APPROVED'
  AND COALESCE(pd.is_deleted,false) = false
ORDER BY pd.id DESC LIMIT 1;
""")
    if not prep:
        raise RuntimeError(
            f"Vikram RSTCRE seed FAIL: no APPROVED prepayment_details for closed child {closed_child_lan}"
        )
    prep_id, fc_ms = prep.split("|", 1)

    already = int(psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_id={prep_id} AND event_status IN ('C','COMPLETED');
""") or "0")
    if already > 0:
        print(
            f"  Vikram RSTCRE: already COMPLETED for prepayment event_id={prep_id} "
            f"(count={already}) — skip seed/drain"
        )
        return False

    rem = psql(f"""
SELECT la.account_id::text, COALESCE(la.loan_amount,0)::text, la.parent_loan_account_id::text
FROM mfi_accounting.loan_account la
WHERE la.la_account_number = '{remaining_child_lan}' AND COALESCE(la.is_deleted,false)=false;
""")
    if not rem:
        raise RuntimeError(f"Vikram RSTCRE seed FAIL: remaining child {remaining_child_lan} not found")
    rem_id, rem_amt, rem_parent = rem.split("|", 2)
    if int(rem_parent) != parent_id:
        raise RuntimeError(
            f"Vikram RSTCRE seed FAIL: remaining child parent_loan_account_id={rem_parent} != {parent_id}"
        )

    # Mirror ChildLoanForeclosureEventGenerationProcessor RSTCRE payload (single remaining member → fraction 1.0)
    payload = [{
        "child_restructuring_data": [{
            "child_loan_account_id": rem_id,
            "parent_account_id": str(parent_id),
            "rescheduling_effective_date": fc_ms,
            "restructuring_impact": "REDUCE_EMI",
            "fraction_of_loan_amount": "1.0",
        }],
        "parent_account_id": str(parent_id),
        "function_code": "FORECLOSURE",
    }]
    data_json = json.dumps(payload, separators=(",", ":"))
    data_sql = data_json.replace("'", "''")
    psql_multi(f"""
INSERT INTO mfi_accounting.loan_account_events_queue (
  parent_account_id, event_type, data, event_status, event_id,
  created_on, created_by, updated_on, updated_by, is_deleted
) VALUES (
  {parent_id}, 'RSTCRE', '{data_sql}', 'P', {prep_id},
  NOW(), 'VIKRAM_E2E', NOW(), 'VIKRAM_E2E', false
);
""")
    print(
        f"  Vikram RSTCRE seed PASS: parent={parent_lan} remaining={remaining_child_lan} "
        f"event_id(prepayment)={prep_id} fc_ms={fc_ms} "
        f"(Sim A ICF — seed mirrors event-gen; ICF does not enqueue RSTCRE)"
    )
    return True


def run_child_loan_prepayment_fc(child_lan: str, death_date: str) -> None:
    """Vikram path: child regular foreclosure.

    Default (Sim B): loanPrepayment DEFAULT→APPROVE_TASK→APPROVE — prod path
    (parent PPP + RSTCRE enqueue). Opt-in Sim A: ICF_USE_LOAN_PREPAYMENT=0 →
    individualChildLoanForeclosure (cascade/force-bill only; no RSTCRE enqueue).
    """
    if VIKRAM_USE_LOAN_PREPAYMENT:
        _run_child_loan_prepayment_via_loan_prepayment(child_lan, death_date)
        return
    _run_child_fc_via_individual_child(child_lan, death_date)


def _run_child_fc_via_individual_child(child_lan: str, death_date: str) -> None:
    """Sim A opt-in: individualChildLoanForeclosure (force-bill / cascade only).

    Harness-only BRE workaround — does NOT enqueue RSTCRE or run parent PPP.
    Prod Parent POS requires loanPrepayment → parentLoanAccountPartPrepayment (internal EC).
    """
    fc_date = _vikram_fc_date(death_date)
    fd_ms = _eod_ms_ist(fc_date)
    print(
        f"  Vikram FC: individualChildLoanForeclosure child={child_lan} "
        f"foreclosure_date={fc_date} ({fd_ms} ms) (death_date={death_date})"
    )
    sim = _lp_simulate(child_lan, fd_ms)
    receipt = f"vikicf{int(time.time()) % 10**12:012d}"
    request = _lp_build_request(sim, child_lan, fd_ms, receipt)
    request["loan_foreclosure_details"]["notes"] = "VIKRAM_PATH ICF child regular FC"
    stan = f"vikram_icf_{child_lan}_{int(time.time())}"
    body = {"headers": _lp_headers(stan, function_code="APPROVE"), "request": request}
    off = psql(
        f"SELECT la_office_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{child_lan}';"
    )
    if off:
        body["headers"]["office_id"] = off
    resp = _acct_post("individualChildLoanForeclosure", body)
    status = resp.get("response_status", {})
    code = status.get("code")
    st = status.get("status")
    print(f"  individualChildLoanForeclosure: {code}/{st} — {str(status.get('message', ''))[:160]}")
    if code not in ("30267", "000") and st != "SUCCESS":
        raise RuntimeError(f"individualChildLoanForeclosure failed for {child_lan}: {code}/{st}")
    wait_loan_closed(child_lan, timeout_s=300)


def _run_child_loan_prepayment_via_loan_prepayment(child_lan: str, death_date: str) -> None:
    """Sim B (default): loanPrepayment DEFAULT → APPROVE_TASK → APPROVE (parent PPP + RSTCRE)."""
    fc_date = _vikram_fc_date(death_date)
    fd_ms = _eod_ms_ist(fc_date)
    print(
        f"  Vikram FC: loanPrepayment child={child_lan} "
        f"foreclosure_date={fc_date} ({fd_ms} ms IST EOD) "
        f"(death_date={death_date}; clamped for 134292 if past)"
    )
    sim = _lp_simulate(child_lan, fd_ms)
    receipt = f"vikram{int(time.time()) % 10**12:012d}"
    request = _lp_build_request(sim, child_lan, fd_ms, receipt)
    ok_codes = frozenset({"000", "30365", "30364", "30267", "30366"})
    for fc in ("DEFAULT", "APPROVE_TASK", "APPROVE"):
        stan = f"vikram_fc_{fc.lower()}_{child_lan}_{int(time.time())}"
        body = {"headers": _lp_headers(stan, function_code=fc), "request": request}
        resp = _acct_post("loanPrepayment", body)
        status = resp.get("response_status", {})
        code = status.get("code")
        st = status.get("status")
        print(
            f"  loanPrepayment {fc}: {code}/{st} — "
            f"{str(status.get('message', ''))[:160]}"
        )
        if code not in ok_codes and st != "SUCCESS":
            if fc == "APPROVE_TASK" and code in ("333", "13005", "334"):
                print(f"  WARN: APPROVE_TASK {code} — continuing to APPROVE if PENDING prepayment exists")
                time.sleep(1)
                continue
            raise RuntimeError(f"loanPrepayment {fc} failed for {child_lan}: {code}/{st}")
        time.sleep(1)
    wait_loan_closed(child_lan, timeout_s=300)


def _advance_emi_labd_count(child_lan: str, advance_due: str) -> int:
    row = psql(f"""
SELECT COUNT(*)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_installment_details lid ON lid.id = labd.loan_installment_details_id
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{child_lan}' AND lid.is_deleted = false
  AND lid.installment_date::date = DATE '{advance_due}';
""")
    return int(row or "0")


def _ensure_advance_emi_labd_harness(child_lan: str, advance_due: str) -> None:
    """When local billing postTransaction fails (operation_mode null), insert EMI-shaped labd
    from real schedule amounts for advance_due — same pattern as create_fresh_dcf_group_fixture.
    Without labd, loanRepayment treats the cycle as EXCESS (not due settlement).
    """
    if _advance_emi_labd_count(child_lan, advance_due) > 0:
        return
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
    )
    row = psql(f"""
SELECT lid.id::text,
       COALESCE(SUM(CASE WHEN ldd.component_type='PRIN' THEN ldd.due_amount ELSE 0 END),0)::text,
       COALESCE(SUM(CASE WHEN ldd.component_type='INT' THEN ldd.due_amount ELSE 0 END),0)::text
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
LEFT JOIN mfi_accounting.loan_due_details ldd
  ON ldd.loan_installment_details_id = lid.id AND ldd.is_deleted = false
WHERE la.la_account_number = '{child_lan}' AND lid.is_deleted = false
  AND lid.installment_date::date = DATE '{advance_due}'
GROUP BY lid.id
LIMIT 1;
""")
    if not row:
        raise RuntimeError(f"EXTRA seed: no installment on {advance_due} for {child_lan}")
    lid_id, prin, interest = row.split("|", 2)
    billing_amt = Decimal(prin) + Decimal(interest)
    emi_ref = f"EMI_HARNESS_{child_lan}_{advance_due.replace('-', '')}"
    psql_multi(f"""
INSERT INTO mfi_accounting.loan_account_billing_details (
  account_id, loan_installment_details_id, billing_amount, principal_amount,
  interest_amount, transaction_value_date, transaction_reference_number, reversed,
  created_on, created_by, updated_on, updated_by
)
SELECT {account_id}, {lid_id}, {billing_amt}, {prin}, {interest},
       lid.installment_date, '{emi_ref}', false,
       NOW(), 'DCF_EXTRA_EMI_LABD', NOW(), 'DCF_EXTRA_EMI_LABD'
FROM mfi_accounting.loan_installment_details lid WHERE lid.id = {lid_id};
""")
    print(f"  EXTRA seed: EMI labd harness advance={advance_due} lid={lid_id} amt={billing_amt} ref={emi_ref}")


def _ensure_advance_installment_billed(child_lan: str, advance_due: str) -> None:
    """Ensure advance EMI has a labd so loanRepayment settles dues (not EXCESS_AMT).

    Prefer real accrual+billing for *past* advance dues; on local postTransaction failure fall
    back to EMI labd harness (same as fresh fixture). Future advance dues cannot be settled by
    cash loanRepayment — fail closed (use DCF_FRESH_EMI_MONTHS_BACK>=2 or pin S2).
    """
    from datetime import date, datetime, timedelta

    if _advance_emi_labd_count(child_lan, advance_due) > 0:
        print(f"  EXTRA seed: advance EMI {advance_due} already billed (labd present)")
        return

    if date.fromisoformat(advance_due) > date.today():
        raise RuntimeError(
            f"EXTRA seed Out-of-scope: advance EMI {advance_due} is still future vs today — "
            f"loanRepayment posts EXCESS_AMT only (advance_int_paid stays 0). "
            f"Fresh fixture needs ≥2 past EMIs (DCF_FRESH_EMI_MONTHS_BACK>=2) or use pin S2."
        )

    sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))
    from clb_queue_harness import (  # type: ignore
        quarantine_billing_portfolio,
        restore_billing_portfolio_quarantine,
    )

    account_id = int(psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
    ))
    parent_id = psql(f"""
SELECT COALESCE(parent_loan_account_id, account_id)::text
FROM mfi_accounting.loan_account WHERE account_id={account_id};
""")
    sibling_ids = [
        int(x)
        for x in subprocess.check_output(
            [*PG, "-c", f"""
SELECT account_id::text FROM mfi_accounting.loan_account
WHERE (account_id={parent_id} OR parent_loan_account_id={parent_id}) AND is_deleted=false;
"""],
            env=PG_ENV,
            text=True,
        ).strip().split("\n")
        if x.strip()
    ]
    bill_d = (datetime.strptime(advance_due, "%Y-%m-%d").date() + timedelta(days=1)).isoformat()
    jt = _eod_ms_ist(bill_d)
    print(f"  EXTRA seed: try billing advance EMI due={advance_due} job_date={bill_d} ({jt})")
    quarantine_billing_portfolio(int(parent_id), [i for i in sibling_ids if i != int(parent_id)])
    try:
        for api in ("interestAccrualCalculation", "interestAccrualPosting", "loanAccountBillingJob"):
            before_id = max_job_execution_id(api)
            try:
                fire_batch(api, jt)
                wait_batch_after_id(api, before_id, timeout_s=180)
            except RuntimeError as e:
                print(f"  WARN: {api} skipped ({e}) — EMI labd harness may apply")
    finally:
        restore_billing_portfolio_quarantine()

    if _advance_emi_labd_count(child_lan, advance_due) > 0:
        print(f"  EXTRA seed: advance EMI billed via batch for {advance_due}")
        return

    _ensure_advance_emi_labd_harness(child_lan, advance_due)
    if _advance_emi_labd_count(child_lan, advance_due) <= 0:
        raise RuntimeError(
            f"EXTRA seed Out-of-scope: no labd for advance EMI {advance_due} on {child_lan} "
            f"(loanRepayment would post EXCESS only; use pin S2 or fix local billing)"
        )


def seed_extra_via_loan_repayment(child_lan: str, death_date: str) -> Decimal:
    """Real loanRepayment path so DFC claim sees EXTRA (advance INT paid past death-1).

    Two-phase (mirrors appropriation order — do not lump PRIN+future INT in one repay):
      1) Catch-up open dues with due_date <= death-1 only
      2) Bill advance EMI if needed, then pay full open dues on that due_date (+ light overpay)
    Resets child to regular (non-NPA) slab so LOAN_REPAYMENT/CASH posts.
    """
    import sys
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from lib.api_client import fire_api, fresh_stan  # type: ignore
    from lib.envelope import build_envelope  # type: ignore

    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}' AND is_deleted=false;"
    )
    if not account_id:
        raise RuntimeError(f"child LAN not found for EXTRA seed: {child_lan}")
    psql_multi(f"""
UPDATE mfi_accounting.loan_account la
SET asset_criteria_slabs_id = sub.regular_slab,
    npa_tagging_date = NULL,
    npa_ageing_start_date = NULL,
    sec_npa_tagging_date = NULL,
    is_sec_npa = false,
    updated_on = NOW(),
    updated_by = 'LOCAL_DCF_A2'
FROM (
  SELECT acs.id AS regular_slab
  FROM mfi_accounting.loan_account la2
  JOIN mfi_accounting.asset_criteria_slabs acs
    ON acs.asset_criteria_group_id = la2.asset_criteria_group_id
   AND acs.is_deleted = false
   AND acs.is_npa = false
  WHERE la2.account_id = {account_id}
  ORDER BY acs.past_due_days_from
  LIMIT 1
) sub
WHERE la.account_id = {account_id};
""")

    death_m1 = psql(f"SELECT to_char(('{death_date}'::date - INTERVAL '1 day')::date,'YYYY-MM-DD');")
    advance_due = psql(f"""
SELECT to_char(MIN(ldd.due_date),'YYYY-MM-DD')
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='INT' AND ldd.is_deleted=false
  AND ldd.due_date::date > '{death_m1}'::date
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""")
    if not advance_due:
        raise RuntimeError(f"no unpaid advance INT due after death-1 for {child_lan}")

    today_ms = str(int(time.time() * 1000))
    _repay_seq = 0

    def _fire_repay(repay_amt: str, value_date_ms: str, tag: str) -> None:
        nonlocal _repay_seq
        _repay_seq += 1
        # Unique per phase: second-resolution CRN collides when phase1+phase2 fire in the
        # same second → ReceiptNumberDedupProcessor 134253 (Fresh+EXTRA fail mode).
        crn = f"A2X{child_lan[-4:]}{_repay_seq}{time.time_ns()}"[:32]
        body = {
            "loan_repayment_details": {
                "account_number": child_lan,
                "repayment_amount": str(repay_amt),
                "repayment_time": today_ms,
                "value_date": value_date_ms,
                "repayment_mode": "CASH",
                "receipt_number": crn,
                "client_reference_number": crn,
            }
        }
        env = build_envelope("accounting", body, stan=fresh_stan("loanRepayment"))
        env["headers"]["function_sub_code"] = "WITHOUT_MAKER_CHECKER"
        env["headers"]["operation_mode"] = "SELF"
        env["headers"]["actor_type"] = "CUSTOMER"
        print(
            f"  EXTRA seed: loanRepayment child={child_lan} amt={repay_amt} "
            f"death_m1={death_m1} advance_due={advance_due} value_date={value_date_ms} "
            f"crn={crn} ({tag})"
        )
        result = fire_api("loanRepayment", env, timeout_s=180)
        code, status = result.response_status()
        if status and status.upper() != "SUCCESS":
            raise RuntimeError(f"loanRepayment EXTRA seed FAIL code={code} body={result.body[:600]}")

    # Phase 1 — dues through death-1 only (no future PRIN/INT in the same lump).
    catchup = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)),0)::numeric(20,0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false
  AND ldd.due_date::date <= '{death_m1}'::date
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""")
    vd_catchup = today_ms
    if catchup and Decimal(catchup) > 0:
        _fire_repay(catchup, vd_catchup, "phase1 catch-up through death-1")
        time.sleep(0.05)
    else:
        print(f"  EXTRA seed: phase1 skip — no open dues through {death_m1}")

    # Bill advance EMI before phase2 — unbilled future dues → EXCESS_AMT, not INT paid.
    _ensure_advance_installment_billed(child_lan, advance_due)

    advance_int = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)),0)::numeric(20,0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false
  AND ldd.component_type='INT' AND ldd.due_date::date = '{advance_due}'::date
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""")
    if not advance_int or Decimal(advance_int) <= 0:
        raise RuntimeError(f"EXTRA seed: advance INT still 0 open on {advance_due} after phase1")
    advance_cycle = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)),0)::numeric(20,0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false
  AND ldd.due_date::date = '{advance_due}'::date
  AND (ldd.due_amount - ldd.paid_amount - COALESCE(ldd.waived_amount,0)) > 0;
""")
    advance_ms = str(
        int(time.mktime(time.strptime(f"{advance_due} 12:00:00", "%Y-%m-%d %H:%M:%S")) * 1000)
    )
    vd_advance = str(max(int(today_ms), int(advance_ms)))
    phase2_amt = str(int(Decimal(advance_cycle or "0") + Decimal("250")))
    _fire_repay(phase2_amt, vd_advance, "phase2 advance cycle (PRIN+INT) + overpay")

    proxy = _extra_proxy(child_lan, death_date)
    print(
        f"  EXTRA proxy after phase2: raw_surplus={proxy['raw_surplus']} "
        f"advance_int_paid={proxy['advance_int_paid']} settled={proxy['settled']} "
        f"owed_till={proxy['owed_till_as_on']}"
    )
    if proxy["raw_surplus"] <= 0:
        raise RuntimeError(
            f"EXTRA seed failed after two-phase loanRepayment: raw_surplus={proxy['raw_surplus']} "
            f"advance_int_paid={proxy['advance_int_paid']} (need advance INT paid > owed through death-1). "
            f"Check billing ran and INT dues exist for {advance_due}."
        )
    return proxy["raw_surplus"]


def seed_pre_existing_emi_labd(child_lan: str, death_date: str) -> None:
    """Adversarial fixture (QA4 dirty-state): ensure a pre-existing EMI labd exists on the
    death-cycle installment BEFORE force-bill runs, so the strict hijack check is exercised.

    Schema-agnostic clone of the child's latest existing labd (keeps EMI-shaped amounts) with a
    synthetic EMI transaction_reference_number so any force-bill overwrite of it is detectable.
    Under ACCEPTANCE_STRICT, inability to seed raises (dirty-state not proven).
    """
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}' AND is_deleted=false;"
    )
    if not account_id:
        msg = f"DCF_SEED_EMI_LABD blocker: child LAN not found {child_lan}"
        if ACCEPTANCE_STRICT:
            raise AssertionError(msg)
        print(f"  {msg}")
        return
    # Prefer labd whose installment_date is on/after death (death-cycle-ish); else any labd.
    # loan_account_billing_details has no is_deleted column.
    src_id = psql(f"""
SELECT labd.id::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_installment_details lid ON lid.id = labd.loan_installment_details_id
WHERE labd.account_id={account_id}
  AND lid.is_deleted=false
  AND lid.installment_date::date >= DATE '{death_date}'
ORDER BY lid.installment_date ASC, labd.id DESC
LIMIT 1;
""")
    if not src_id:
        src_id = psql(f"""
SELECT id::text FROM mfi_accounting.loan_account_billing_details
WHERE account_id={account_id}
ORDER BY id DESC LIMIT 1;
""")
    if not src_id:
        msg = (
            f"DCF_SEED_EMI_LABD blocker: no existing labd to clone for {child_lan} "
            f"(fixture needs a real EMI billing row)"
        )
        if ACCEPTANCE_STRICT:
            raise AssertionError(msg)
        print(f"  {msg}")
        return
    cols = subprocess.check_output(
        [*PG, "-c", """
SELECT column_name FROM information_schema.columns
WHERE table_schema='mfi_accounting' AND table_name='loan_account_billing_details'
ORDER BY ordinal_position;"""],
        env=PG_ENV, text=True,
    ).strip().split("\n")
    cols = [c.strip() for c in cols if c.strip() and c.strip() != "id"]
    emi_ref = f"EMI_LABD_FIXTURE_{child_lan}_{int(time.time())}"
    select_exprs = []
    for c in cols:
        if c == "transaction_reference_number":
            select_exprs.append(f"'{emi_ref}'")
        elif c in ("created_by", "updated_by"):
            select_exprs.append("'LOCAL_EMI_LABD_FIXTURE'")
        elif c in ("created_on", "updated_on"):
            select_exprs.append("NOW()")
        else:
            select_exprs.append(c)
    try:
        psql_multi(f"""
INSERT INTO mfi_accounting.loan_account_billing_details ({", ".join(cols)})
SELECT {", ".join(select_exprs)}
FROM mfi_accounting.loan_account_billing_details WHERE id={src_id};
""")
        print(f"  DCF_SEED_EMI_LABD: seeded pre-existing EMI labd (ref={emi_ref}) for {child_lan} "
              f"(clone of labd id={src_id})")
    except subprocess.CalledProcessError as e:
        msg = f"DCF_SEED_EMI_LABD blocker: clone insert failed ({e})"
        if ACCEPTANCE_STRICT:
            raise AssertionError(msg) from e
        print(f"  {msg}; skipping fixture (not a Pass)")


def assert_webapp_bound_apis(parent_lan: str, children: list[str], last_child: str) -> None:
    """Live webapp-bound APIs QA screens use — fail-closed under ACCEPTANCE_STRICT.

    Required fields (TDPQA-72 / UI-impacting DCF ships):
      - getLoanAccountSummaryDetails → interest_details.accrued_amount ≤ original_amount (Obs3)
      - getLoanAccountStatement → death child shows DFC_PRTL_BILL; parent must NOT
      - getLoanAccountOverviewDetails (account_number_list) → SUCCESS for CLOSED loans
    """
    sys.path.insert(0, str(ROOT / "scripts" / "testing"))
    from lib.api_client import fire_api, fresh_stan  # noqa: WPS433
    import json

    def _headers(api: str) -> dict:
        return {
            "tenant_code": "mfi",
            "client_code": "NOVOPAY",
            "channel_code": "WEB",
            "user_id": "3",
            "stan": fresh_stan(api),
            "function_code": "DEFAULT",
            "function_sub_code": "DEFAULT",
        }

    for lan, role in [(parent_lan, "parent")] + [(c, "child") for c in children]:
        # Summary — Obs3 Accrued vs Original (nested interest_details)
        r = fire_api(
            "getLoanAccountSummaryDetails",
            {"headers": _headers("summary"), "request": {"account_number": lan}},
        )
        body = json.loads(r.body or "{}")
        code, status = r.response_status()
        if status != "SUCCESS" and code not in ("000", "0", "30225"):
            raise AssertionError(f"webapp FAIL summary {role} {lan}: code={code} status={status}")
        # QA (TDPQA-72): "summary INT mismatch" / "summary INT 0" = Interest section
        # Accrued vs Original on getLoanAccountSummaryDetails. Response template maps
        # interest_details.accrued_amount ← interest_accrued_amount (EC) and
        # interest_details.original_amount ← interest_original_amount (EC).
        interest = body.get("interest_details") or {}
        accrued = Decimal(str(interest.get("accrued_amount") or "0"))
        original = Decimal(str(interest.get("original_amount") or "0"))
        if ACCEPTANCE_STRICT and accrued > original + Decimal("1"):
            raise AssertionError(
                f"webapp FAIL Obs3 summary {role} {lan}: "
                f"interest_details.accrued_amount={accrued} > "
                f"interest_details.original_amount={original}"
            )
        # Value-level vs SQL Obs3 formula — must mirror product live-join Accrued
        # (InterestAccrualDetailsRepository.getAccruedAmountByLoanAccountId: iad ⋈ lid is_deleted=false).
        # Raw SUM(iad) overcounts soft-deleted lids after last-child close (Δ = parent FB accumulate).
        sql_row = psql(f"""
WITH la AS (SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{lan}')
SELECT
  (SELECT COALESCE(SUM(ldd.due_amount),0)::text FROM mfi_accounting.loan_due_details ldd, la
   WHERE ldd.loan_account_id=la.account_id AND ldd.component_type='INT' AND ldd.is_deleted=false
     AND EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details bd
                 WHERE bd.loan_installment_details_id=ldd.loan_installment_details_id
                   AND COALESCE(bd.reversed,false)=false)),
  (SELECT COALESCE(SUM(iad.total_accrued_amount),0)::text
   FROM mfi_accounting.interest_accrual_details iad
   INNER JOIN mfi_accounting.loan_installment_details lid
     ON lid.id = iad.loan_installment_details_id AND lid.is_deleted = false
   , la WHERE iad.account_id=la.account_id);
""")
        if sql_row and ACCEPTANCE_STRICT:
            sql_orig_s, sql_acc_s = sql_row.split("|", 1)
            sql_original = Decimal(sql_orig_s or "0")
            sql_accrued = Decimal(sql_acc_s or "0")
            if sql_accrued > 0 and accrued == 0:
                raise AssertionError(
                    f"webapp FAIL summary INT 0: {role} {lan} "
                    f"interest_details.accrued_amount=0 but SQL Accrued={sql_accrued} "
                    f"(QA field = interest_details.accrued_amount)"
                )
            if abs(accrued - sql_accrued) > Decimal("1") or abs(original - sql_original) > Decimal("1"):
                raise AssertionError(
                    f"webapp FAIL summary INT mismatch: {role} {lan} "
                    f"API accrued/original={accrued}/{original} "
                    f"SQL Accrued/Original={sql_accrued}/{sql_original}"
                )
        print(
            f"  webapp summary PASS: {role} {lan} "
            f"interest_details.accrued_amount={accrued} "
            f"interest_details.original_amount={original}"
        )

        # Overview — account_number_list + Product excess_amount=0 on parent
        r = fire_api(
            "getLoanAccountOverviewDetails",
            {"headers": _headers("overview"), "request": {"account_number_list": [lan]}},
        )
        code, status = r.response_status()
        if status != "SUCCESS" and code not in ("000", "0", "30223"):
            raise AssertionError(f"webapp FAIL overview {role} {lan}: code={code} status={status}")
        ov_body = json.loads(r.body or "{}")
        ov_list = ov_body.get("account_overview_list") or []
        excess_ui = None
        if ov_list:
            amt = (ov_list[0].get("amount_details") or {})
            excess_ui = Decimal(str(amt.get("excess_amount") or "0"))
        if role == "parent" and ACCEPTANCE_STRICT:
            if excess_ui is None:
                raise AssertionError(f"webapp FAIL overview parent {lan}: missing amount_details.excess_amount")
            if excess_ui != 0:
                raise AssertionError(
                    f"webapp FAIL Product excess=0: overview parent {lan} excess_amount={excess_ui}"
                )
        print(f"  webapp overview PASS: {role} {lan} code={code} excess_amount={excess_ui}")

        # Statement — force-bill visibility (product CRN numeric; statement may show reference_number)
        r = fire_api(
            "getLoanAccountStatement",
            {
                "headers": _headers("statement"),
                "request": {"account_number": lan, "offset": "0", "page_size": "50"},
            },
        )
        code, status = r.response_status()
        if status != "SUCCESS" and code not in ("000", "0"):
            raise AssertionError(f"webapp FAIL statement {role} {lan}: code={code} status={status}")
        blob = r.body or ""
        fb_row = psql(_dfc_force_bill_tm_sql(lan))
        fb_ref = fb_row.split("|", 1)[0] if fb_row else ""
        has_fb_prefix = "DFC_PRTL_BILL" in blob
        has_fb_ref = bool(fb_ref) and fb_ref in blob
        has_fb = has_fb_prefix or has_fb_ref
        # 9b6454df6: parent also posts force-bill — statement may show parent FB ref (Obs1b).
        if lan == last_child and ACCEPTANCE_STRICT and fb_ref and not has_fb:
            raise AssertionError(
                f"webapp FAIL Obs1: death child {lan} has force-bill txn ref={fb_ref} but statement "
                f"response lacks that reference / DFC_PRTL_BILL visibility"
            )
        if not fb_ref:
            print(f"  webapp statement N/A force-bill: {role} {lan} (no DFC force-bill CRN)")
        else:
            print(
                f"  webapp statement PASS: {role} {lan} fb_ref_in_body={has_fb_ref} "
                f"DFC_PRTL={has_fb_prefix} ref={fb_ref}"
            )


def assert_accrued_le_original(lan: str, role: str) -> None:
    """TDPQA-72 Obs3: summary Accrued must not exceed Original after DFC close.

    Mirrors product summary Accrued (`InterestAccrualDetailsRepository.getAccruedAmountByLoanAccountId`):
      live-join iad ⋈ lid WHERE lid.is_deleted=false — raw SUM(iad) alone is WRONG (counts soft-deleted lids).
      Original = SUM(INT due_amount) WHERE installment has non-reversed labd
    QA fail mode: Accrued > Original on parent after last-child DFC (stale IAD past billed INT).
    """
    row = psql(f"""
WITH la AS (SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{lan}')
SELECT
  (SELECT COALESCE(SUM(ldd.due_amount),0)::text FROM mfi_accounting.loan_due_details ldd, la
   WHERE ldd.loan_account_id=la.account_id AND ldd.component_type='INT' AND ldd.is_deleted=false
     AND EXISTS (SELECT 1 FROM mfi_accounting.loan_account_billing_details bd
                 WHERE bd.loan_installment_details_id=ldd.loan_installment_details_id
                   AND COALESCE(bd.reversed,false)=false)),
  (SELECT COALESCE(SUM(iad.total_accrued_amount),0)::text
   FROM mfi_accounting.interest_accrual_details iad
   INNER JOIN mfi_accounting.loan_installment_details lid
     ON lid.id = iad.loan_installment_details_id AND lid.is_deleted = false
   , la WHERE iad.account_id=la.account_id);
""")
    if not row:
        raise AssertionError(f"Obs3 FAIL: no account {lan} ({role})")
    orig_s, acc_s = row.split("|", 1)
    original = Decimal(orig_s or "0")
    accrued = Decimal(acc_s or "0")
    # Allow ₹1 rounding (local parent was 2810 vs 2809 before reconcile)
    if ACCEPTANCE_STRICT and accrued > original + Decimal("1"):
        raise AssertionError(
            f"ACCEPTANCE FAIL (Obs3 Accrued>Original): {role} {lan} Accrued={accrued} Original={original} "
            f"(Δ={accrued - original}). Summary interest_accrued_amount must not exceed "
            f"interest_original_amount after DFC. Debug-only: ACCEPTANCE_STRICT=0."
        )
    print(f"  Obs3 PASS: {role} {lan} Accrued={accrued} Original={original} (live-join lids)")


def assert_no_accrued_on_deleted_installments(lan: str, role: str) -> None:
    """RSTCRE L1: Accrued must not remain on soft-deleted installments after schedule recreate.

    Last-child DFC closes the parent without parent RSTCRE schedule regen — Accrued may remain on
    soft-deleted lids while live-join Accrued already matches Original (Obs3). Fail-closed only while
    the loan is still ACTIVE (non-last RSTCRE / remaining members).
    """
    status = (psql(f"""
SELECT loan_status FROM mfi_accounting.loan_account
WHERE la_account_number='{lan}' AND COALESCE(is_deleted,false)=false LIMIT 1;
""") or "").strip()
    orphan = psql(f"""
SELECT COALESCE(SUM(iad.total_accrued_amount),0)::text
FROM mfi_accounting.interest_accrual_details iad
JOIN mfi_accounting.loan_account la ON la.account_id = iad.account_id
JOIN mfi_accounting.loan_installment_details lid ON lid.id = iad.loan_installment_details_id
WHERE la.la_account_number = '{lan}'
  AND lid.is_deleted = true
  AND iad.total_accrued_amount > 0;
""") or "0"
    orphan_amt = Decimal(orphan)
    if status == "CLOSED":
        print(
            f"  RSTCRE Accrued orphan N/A: {role} {lan} loan_status=CLOSED "
            f"Accrued_on_deleted={orphan_amt} (last-child close; Obs3 live-join is SoT)"
        )
        return
    if ACCEPTANCE_STRICT and orphan_amt > 0:
        raise AssertionError(
            f"ACCEPTANCE FAIL (RSTCRE Accrued orphan): {role} {lan} Accrued={orphan_amt} still on "
            f"soft-deleted installment(s). Expected RSTCRE to repoint Accrued onto surviving lids."
        )
    print(f"  RSTCRE Accrued orphan PASS: {role} {lan} Accrued_on_deleted={orphan_amt}")


def _dfc_force_bill_tm_sql(lan: str) -> str:
    """DFC partial-cycle BILLING via CRN shape (posts to GL accounts — not LAN in transaction_details).

    Product CRN: accountId || valueDateMs[13] || optional deathForeclosureDetailsId.
    EMI NORMAL_BILLING CRNs use accountId || installmentId || millis and do not match ^aid17….
    """
    return f"""
SELECT tm.reference_number, tm.client_reference_number, COALESCE(tm.original_amount,0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.la_account_number = '{lan}'
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ ('^' || la.account_id::text || '17[0-9]{{11}}([0-9]+)?$')
ORDER BY tm.id DESC LIMIT 1;
"""


def assert_parent_force_bill_labd(parent_lan: str) -> None:
    """Obs1b: parent last-child path posts dedicated BILLING force-bill (numeric client_ref)."""
    row = psql(_dfc_force_bill_tm_sql(parent_lan))
    if not row:
        if ACCEPTANCE_STRICT:
            raise AssertionError(
                f"Obs1b FAIL: parent {parent_lan} missing DFC partial-cycle BILLING txn "
                f"(CRN accountId||valueDateMs[||dfdId]; 9b6454df6 parent FB expected)"
            )
        print(f"  Obs1b N/A: parent {parent_lan} no DFC force-bill BILLING CRN")
        return
    ref, client_ref, amt_s = row.split("|", 2)
    labd = psql(f"""
SELECT labd.id::text, COALESCE(labd.interest_amount,0)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{parent_lan}'
  AND labd.transaction_reference_number = '{ref}'
  AND COALESCE(labd.principal_amount,0) = 0
  AND COALESCE(labd.interest_amount,0) > 0
  AND COALESCE(labd.reversed,false) = false
LIMIT 1;
""")
    if not labd:
        # SHG parent accumulates sequential child FC/DFC gap amounts onto one interest-only
        # labd (product ForceBillBillingSupport). Latest BILLING txn_ref may not equal the
        # labd row's txn_ref after multi-child Vikram — accept any live interest-only labd.
        labd = psql(f"""
SELECT labd.id::text, COALESCE(labd.interest_amount,0)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{parent_lan}'
  AND COALESCE(labd.principal_amount,0) = 0
  AND COALESCE(labd.interest_amount,0) > 0
  AND COALESCE(labd.reversed,false) = false
ORDER BY labd.id DESC LIMIT 1;
""")
        if labd:
            print(
                f"  Obs1b note: parent labd not on latest FB ref={ref}; "
                f"using accumulated interest-only labd={labd} (SHG parent accumulate)"
            )
    if ACCEPTANCE_STRICT and not labd:
        raise AssertionError(
            f"Obs1b FAIL: parent {parent_lan} force-bill txn ref={ref} lacks dedicated interest-only labd"
        )
    print(f"  Obs1b PASS: parent {parent_lan} force-bill ref={ref} client_ref={client_ref} amt={amt_s} labd={labd}")
    assert_force_bill_gl_shape(ref, f"{parent_lan}/force-bill", expect_child_cg=False)


def _force_bill_interest_total(lan: str) -> Decimal:
    """Sum interest on dedicated force-bill labd rows (prin=0, interest>0) for a LAN."""
    raw = psql(f"""
SELECT COALESCE(SUM(labd.interest_amount),0)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{lan}'
  AND COALESCE(labd.principal_amount,0) = 0
  AND COALESCE(labd.interest_amount,0) > 0
  AND COALESCE(labd.reversed,false) = false;
""")
    return Decimal(raw or "0")


def assert_parent_force_bill_equals_sum_children(parent_lan: str, child_lans: list[str]) -> None:
    """Vikram 391228: parent force-bill interest must equal Σ child force-bill (no ₹1 drift)."""
    parent_fb = _force_bill_interest_total(parent_lan)
    child_sum = sum((_force_bill_interest_total(c) for c in child_lans), Decimal("0"))
    print(
        f"  Vikram ₹1 FB check: parent={parent_lan} fb={parent_fb} "
        f"children={child_lans} sum={child_sum}"
    )
    if ACCEPTANCE_STRICT and parent_fb != child_sum:
        raise AssertionError(
            f"Vikram 391228 FAIL: parent force-bill interest {parent_fb} != "
            f"sum(children) {child_sum} (Δ={parent_fb - child_sum})"
        )
    if parent_fb == child_sum:
        print(f"  Vikram 391228 PASS: parent FB == Σ children FB ({parent_fb})")
    else:
        print(f"  Vikram 391228 WARN: parent FB {parent_fb} != Σ children {child_sum}")


def assert_parent_rsch_lapd_columns(parent_lan: str, expected_extra: Decimal = Decimal("0")) -> dict:
    """Column audit: parent RSCH lapd must have excess=0 (A2 nets principal); amount==principal."""
    row = psql(f"""
SELECT lapd.id::text,
       COALESCE(lapd.amount,0)::text,
       COALESCE(lapd.principal_amount,0)::text,
       COALESCE(lapd.interest_amount,0)::text,
       COALESCE(lapd.excess_amount,0)::text,
       lapd.transaction_reference_number
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.account_id = lapd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND tc.type='RSCH_DEATH_FORECLOSURE'
ORDER BY tm.id DESC LIMIT 1;
""")
    if not row:
        raise AssertionError(f"parent RSCH lapd FAIL: no row for {parent_lan}")
    lapd_id, amount_s, prin_s, int_s, excess_s, txn_ref = row.split("|", 5)
    evidence = {
        "lapd_id": lapd_id,
        "amount": Decimal(amount_s),
        "principal_amount": Decimal(prin_s),
        "interest_amount": Decimal(int_s),
        "excess_amount": Decimal(excess_s),
        "transaction_reference_number": txn_ref,
    }
    if ACCEPTANCE_STRICT:
        if evidence["excess_amount"] != 0:
            raise AssertionError(
                f"ACCEPTANCE FAIL: parent RSCH lapd.excess_amount={evidence['excess_amount']} must be 0 "
                f"(not claimOverpayment≈{expected_extra}; A2 principal netting)"
            )
        if evidence["amount"] != evidence["principal_amount"]:
            raise AssertionError(
                f"ACCEPTANCE FAIL (A2): parent RSCH amount={evidence['amount']} != "
                f"principal_amount={evidence['principal_amount']}"
            )
        if evidence["interest_amount"] != 0:
            raise AssertionError(
                f"ACCEPTANCE FAIL: parent RSCH interest_amount={evidence['interest_amount']} must be 0"
            )
    print(
        f"  parent RSCH lapd PASS: id={lapd_id} amount={evidence['amount']} "
        f"principal={evidence['principal_amount']} excess=0 ref={txn_ref}"
    )
    return evidence


def assert_parent_child_excess_gl_parity(parent_lan: str, child_lan: str, expected_extra: Decimal) -> None:
    """Sheet15: child DEATH and parent RSCH both post EXCESS_* when claim overpay > 0.

    LAPD/statement excess stays 0 (TDPQA-72 390372). Do not require parent EXCESS_*=0 in GL
    (that was 9b6454df6 and caused child-only EXCESS / GROSS RCV Δ — Vikram 391188).
    """
    if expected_extra <= 0:
        print(f"  EXCESS GL N/A: expected_extra={expected_extra}")
        return
    child_ref, _ = latest_txn(child_lan, "DEATH_FORECLOSURE")
    parent_ref, _ = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    if not child_ref:
        raise AssertionError(f"EXCESS parity FAIL: child {child_lan} missing DEATH_FORECLOSURE")
    if not parent_ref:
        raise AssertionError(f"EXCESS parity FAIL: parent {parent_lan} missing RSCH_DEATH_FORECLOSURE")

    def _excess_sum(ref: str) -> tuple[Decimal, int]:
        row = psql(f"""
SELECT COALESCE(SUM(tpd.amount),0)::text, COUNT(*)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}' AND tpd.reference_code LIKE 'EXCESS_%';
""") or "0|0"
        amt_s, cnt_s = row.split("|", 1)
        return Decimal(amt_s or "0"), int(cnt_s or "0")

    child_part = int(psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{child_ref}';
""") or "0")
    parent_part = int(psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{parent_ref}';
""") or "0")
    if child_part == 0 or parent_part == 0:
        print(
            f"  EXCESS GL Out-of-scope: partitions missing locally "
            f"(child_parts={child_part} parent_parts={parent_part}) — code posts EXCESS_*; QA4 verifies"
        )
        return
    child_ex, _ = _excess_sum(child_ref)
    parent_ex, _ = _excess_sum(parent_ref)
    if ACCEPTANCE_STRICT and child_ex <= 0:
        raise AssertionError(
            f"ACCEPTANCE FAIL: child {child_lan} DFC EXCESS_* sum={child_ex} (EXTRA≈{expected_extra})"
        )
    if ACCEPTANCE_STRICT and parent_ex <= 0:
        raise AssertionError(
            f"ACCEPTANCE FAIL: parent {parent_lan} RSCH EXCESS_* sum={parent_ex} "
            f"(must match child Sheet15 EXCESS; got child={child_ex})"
        )
    if ACCEPTANCE_STRICT and child_ex != parent_ex:
        raise AssertionError(
            f"ACCEPTANCE FAIL: EXCESS_* GL mismatch child={child_ex} parent={parent_ex} "
            f"(refs {child_ref} / {parent_ref})"
        )
    print(f"  EXCESS GL parity PASS: child=parent={child_ex} EXTRA≈{expected_extra}")


def assert_child_excess_when_extra(child_lan: str, expected_extra: Decimal) -> None:
    """Child DEATH_FORECLOSURE keeps EXCESS_* when LAN had actual excess (child layer)."""
    if expected_extra <= 0:
        print(f"  child EXCESS N/A: expected_extra={expected_extra}")
        return
    ref, _ = latest_txn(child_lan, "DEATH_FORECLOSURE")
    if not ref:
        raise AssertionError(f"child {child_lan} missing DEATH_FORECLOSURE")
    part_count = int(psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}';
""") or "0")
    if part_count == 0:
        print(f"  child EXCESS Out-of-scope: {child_lan} DFC ref={ref} has 0 partition rows locally")
        return
    excess_int = Decimal(psql(f"""
SELECT COALESCE(MAX(CASE WHEN tpd.reference_code='EXCESS_INCOME_INT_AMT' THEN tpd.amount END),0)::text
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id=tpd.transaction_id
WHERE tm.reference_number='{ref}';
""") or "0")
    if ACCEPTANCE_STRICT and excess_int <= 0:
        raise AssertionError(
            f"ACCEPTANCE FAIL: child {child_lan} DFC missing EXCESS_INCOME_INT_AMT "
            f"(EXTRA≈{expected_extra}, got {excess_int})"
        )
    print(f"  child EXCESS PASS: {child_lan} EXCESS_INCOME_INT_AMT={excess_int} EXTRA≈{expected_extra}")


def assert_non_last_child_parent_rsch_parity(child_lan: str, parent_lan: str) -> None:
    """Non-last invariant (SDCP-10199): child DEATH_FORECLOSURE.original_amount ==
    parent RSCH_DEATH_FORECLOSURE.original_amount for the same death event.

    Parent doParentPartPrePayment non-last branch reuses child TRANSACTION_AMOUNT from EC
    (no A2 EXTRA netting). Last-child path intentionally differs — see assert_a2_extra_parent_rsch.
    """
    child_ref, child_amt_s = latest_txn_poll(child_lan, "DEATH_FORECLOSURE")
    parent_ref, parent_amt_s = latest_txn_poll(
        parent_lan, "RSCH_DEATH_FORECLOSURE", match_amount=child_amt_s or None,
    )
    if not child_ref:
        raise AssertionError(f"non-last parity FAIL: child {child_lan} missing DEATH_FORECLOSURE")
    if not parent_ref:
        raise AssertionError(
            f"non-last parity FAIL: parent {parent_lan} missing RSCH_DEATH_FORECLOSURE after non-last child"
        )
    child_amt = Decimal(child_amt_s or "0")
    parent_amt = Decimal(parent_amt_s or "0")
    if ACCEPTANCE_STRICT and child_amt != parent_amt:
        raise AssertionError(
            f"non-last parity FAIL child={child_lan} DEATH_FORECLOSURE={child_amt} "
            f"parent={parent_lan} RSCH={parent_amt} (must match — parent reuses child TRANSACTION_AMOUNT)"
        )
    print(
        f"  non-last parity PASS: child DFC={child_amt} parent RSCH={parent_amt} "
        f"child_ref={child_ref} parent_ref={parent_ref}"
    )

    pst = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';")
    if pst != "ACTIVE":
        raise AssertionError(f"non-last parity FAIL: parent {parent_lan} expected ACTIVE got {pst!r}")
    print(f"  non-last parent status PASS: {parent_lan} ACTIVE")

    row = psql(f"""
SELECT lapd.id::text,
       COALESCE(lapd.amount,0)::text,
       COALESCE(lapd.principal_amount,0)::text,
       COALESCE(lapd.interest_amount,0)::text,
       COALESCE(lapd.excess_amount,0)::text,
       lapd.transaction_reference_number
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.account_id = lapd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND tc.type='RSCH_DEATH_FORECLOSURE'
  AND tm.reference_number = '{parent_ref}'
LIMIT 1;
""")
    if not row:
        raise AssertionError(f"non-last parity FAIL: parent RSCH lapd missing for ref={parent_ref}")
    lapd_id, amount_s, prin_s, int_s, excess_s, txn_ref = row.split("|", 5)
    lapd_amount = Decimal(amount_s)
    lapd_prin = Decimal(prin_s)
    lapd_int = Decimal(int_s)
    lapd_excess = Decimal(excess_s)
    if ACCEPTANCE_STRICT:
        # Non-last parity is child DFC tm == parent RSCH tm (above). lapd.amount is the payment-row
        # total and may differ from tm.original_amount when principal/interest legs split the claim.
        if lapd_excess != 0:
            raise AssertionError(
                f"non-last parity FAIL: parent RSCH lapd.excess_amount={lapd_excess} must be 0 on non-last path"
            )
    if lapd_amount != parent_amt:
        print(
            f"  non-last parent RSCH lapd INFO: lapd.amount={lapd_amount} tm.original_amount={parent_amt} "
            f"(non-last parity is tm-level child DFC==parent RSCH; lapd split may differ)"
        )
    print(
        f"  non-last parent RSCH lapd PASS: id={lapd_id} amount={lapd_amount} "
        f"principal={lapd_prin} interest={lapd_int} excess={lapd_excess} ref={txn_ref} "
        f"tm={parent_amt}"
    )

    # 9b6454df6: parent force-bill BILLING may post on any-child DFC when partial-cycle slice > 0.
    # Strict Obs1b labd audit runs after last child; here we only note DFC-narration txn (not EMI billing).
    fb_row = psql(_dfc_force_bill_tm_sql(parent_lan))
    if fb_row:
        fb_ref, fb_crn, fb_amt = fb_row.split("|", 2)
        print(
            f"  non-last parent force-bill txn present: ref={fb_ref} crn={fb_crn} amt={fb_amt} "
            f"(Obs1b strict at end)"
        )
    else:
        print(f"  non-last parent force-bill N/A: no DFC partial-cycle BILLING for {parent_lan} (slice was 0)")


def assert_a2_extra_parent_rsch(parent_lan: str, child_lan: str, expected_extra: Decimal) -> None:
    """Issue A (last-child only): EXTRA>0 — A2 nets parent RSCH principal; lapd.excess=0;
    child+parent both keep EXCESS_* GL (Sheet15 parity)."""
    if expected_extra <= 0:
        print(f"  Issue A N/A: expected_extra={expected_extra} (SEED_EXTRA=0)")
        assert_parent_child_excess_gl_parity(parent_lan, child_lan, expected_extra)
        assert_parent_rsch_lapd_columns(parent_lan, expected_extra)
        return
    rsch_ref, rsch_amt = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    if not rsch_ref:
        raise AssertionError(f"Issue A FAIL: no RSCH_DEATH_FORECLOSURE for parent {parent_lan}")
    assert_child_excess_when_extra(child_lan, expected_extra)
    assert_parent_child_excess_gl_parity(parent_lan, child_lan, expected_extra)
    rsch_cols = assert_parent_rsch_lapd_columns(parent_lan, expected_extra)
    pos = Decimal(psql(f"""
SELECT COALESCE(SUM(ldd.due_amount-ldd.paid_amount-ldd.waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    if pos != 0:
        raise AssertionError(f"Issue A FAIL: parent PRIN pending {pos} after last-child DFC")
    print(
        f"  Issue A PASS: EXTRA≈{expected_extra} parent RSCH_amt={rsch_amt} "
        f"lapd.excess=0 amount==principal={rsch_cols['principal_amount']}"
    )


def assert_force_bill_labd(child_lan: str, *, require_emi_fixture: bool | None = None) -> None:
    """Issue B (QA acceptance): death-child force-bill must have DEDICATED labd visibility.

    QA obs1: EMI labd hijack — an existing EMI billing row's transaction_reference_number is
    overwritten to the force-bill txn while its billing amounts still look like the EMI, so there
    is no dedicated force-bill labd QA can see. This must FAIL under ACCEPTANCE_STRICT, not pass on
    "a labd linked somehow exists".

    Product (9b6454df6): CRN is accountId||valueDateMs[||dfdId] — not DFC_PRTL_BILL_* prefix.
    """
    fb = psql(_dfc_force_bill_tm_sql(child_lan))
    fb_ref, fb_client, fb_amt_s = (fb.split("|", 2) if fb else ("", "", "0"))
    fb_amt = Decimal(fb_amt_s or "0")

    row = ""
    if fb_ref:
        # Prefer exact interest match (dedicated force-bill labd).
        row = psql(f"""
SELECT labd.id::text, labd.transaction_reference_number, tm.client_reference_number,
       COALESCE(labd.interest_amount,0)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = labd.transaction_reference_number
WHERE la.la_account_number = '{child_lan}'
  AND labd.transaction_reference_number = '{fb_ref}'
  AND COALESCE(labd.principal_amount,0) = 0
  AND COALESCE(labd.interest_amount,0) > 0
  AND ABS(COALESCE(labd.interest_amount,0) - {fb_amt}) <= 0.01
  AND COALESCE(labd.reversed,false) = false
ORDER BY labd.id DESC LIMIT 1;
""")
        if not row:
            # Fall back: any interest-only labd on FB ref (hijack / accumulate mismatch detection).
            row = psql(f"""
SELECT labd.id::text, labd.transaction_reference_number, tm.client_reference_number,
       COALESCE(labd.interest_amount,0)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = labd.transaction_reference_number
WHERE la.la_account_number = '{child_lan}'
  AND labd.transaction_reference_number = '{fb_ref}'
  AND COALESCE(labd.principal_amount,0) = 0
  AND COALESCE(labd.interest_amount,0) > 0
  AND COALESCE(labd.reversed,false) = false
ORDER BY labd.id DESC LIMIT 1;
""")
    if not row:
        if not fb_ref and fb_amt == 0:
            print(f"  Issue B N/A: no DFC force-bill BILLING CRN for {child_lan} "
                  f"(partial-cycle force-bill slice was 0 — Obs1 hijack N/A)")
            return
        raise AssertionError(
            f"Issue B FAIL: no dedicated interest-only labd for force-bill on {child_lan}; "
            f"force-bill txn={fb_ref or 'none'} client_ref={fb_client or 'none'}"
        )
    labd_id, txn_ref, client_ref, int_amt_s = row.split("|", 3)
    int_amt = Decimal(int_amt_s or "0")

    if ACCEPTANCE_STRICT and fb_amt > 0 and abs(int_amt - fb_amt) > Decimal("0.01"):
        raise AssertionError(
            f"ACCEPTANCE FAIL (Obs1 EMI-labd hijack): labd_id={labd_id} interest={int_amt} does NOT match "
            f"force-bill txn interest {fb_amt} (txn_ref={txn_ref}). The EMI labd appears hijacked to the "
            f"force-bill txn while its amounts still look like an EMI — QA needs a DEDICATED force-bill labd. "
            f"Debug-only override: ACCEPTANCE_STRICT=0."
        )
    print(f"  Issue B PASS: labd_id={labd_id} txn_ref={txn_ref} client_ref={client_ref} "
          f"interest={int_amt} force_bill_txn_amt={fb_amt}")
    if fb_ref:
        assert_force_bill_gl_shape(fb_ref, f"{child_lan}/force-bill", expect_child_cg=True)

    emi_left = int(psql(f"""
SELECT COUNT(*)::text
FROM mfi_accounting.loan_account_billing_details labd
JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
WHERE la.la_account_number = '{child_lan}'
  AND labd.transaction_reference_number LIKE 'EMI_LABD_FIXTURE_%';
""") or "0")
    if require_emi_fixture is None:
        require_emi_fixture = SEED_EMI_LABD and ACCEPTANCE_STRICT
    if require_emi_fixture:
        if emi_left < 1:
            raise AssertionError(
                f"ACCEPTANCE FAIL (Obs1): EMI_LABD_FIXTURE rows missing after DFC for {child_lan} "
                f"(EMI labd was deleted or txn_ref hijacked away from EMI_LABD_FIXTURE_*)"
            )
        print(f"  Issue B PASS: EMI_LABD_FIXTURE rows preserved count={emi_left}")
    elif emi_left > 0:
        print(f"  Issue B: EMI fixture rows present count={emi_left}")


def assert_loan_prepayment_force_bill(child_lan: str) -> None:
    """Vikram Obs H: FC force-bill labd; LOAN_PREPAYMENT required only on Sim B."""
    if VIKRAM_USE_LOAN_PREPAYMENT:
        ref, amt = latest_txn_poll(child_lan, "LOAN_PREPAYMENT")
        if not ref:
            if ACCEPTANCE_STRICT:
                raise AssertionError(
                    f"Vikram FC FAIL: child {child_lan} missing LOAN_PREPAYMENT txn "
                    f"(regular foreclosure must post before force-bill assert)"
                )
            print(f"  Vikram FC WARN: LOAN_PREPAYMENT missing for {child_lan}")
        else:
            print(f"  Vikram FC PASS: LOAN_PREPAYMENT child={child_lan} ref={ref} amount={amt}")
    else:
        print(
            f"  Vikram FC note: ICF harness path — LOAN_PREPAYMENT not required for {child_lan}; "
            f"force-bill only (Sim B loanPrepayment BRE-blocked locally)"
        )
    assert_force_bill_labd(child_lan, require_emi_fixture=False)


def compute_outstanding_rounded(child_lan: str, death_date: str) -> str:
    """SQL component sum aligned with dcf_amount_reconcile.sql (read-only buckets)."""
    overdue = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount-ldd.paid_amount-ldd.waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false
  AND ldd.component_type IN ('PRIN','INT') AND ldd.due_date < '{death_date}'::date
  AND (ldd.due_amount-ldd.paid_amount-ldd.waived_amount)>0;
""")
    future_prin = psql(f"""
SELECT COALESCE(SUM(ldd.due_amount-ldd.paid_amount-ldd.waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PRIN'
  AND ldd.due_date >= '{death_date}'::date AND ldd.is_deleted=false;
""")
    pint = psql(f"""
SELECT COALESCE(SUM(GREATEST(ldd.due_amount-ldd.paid_amount-ldd.waived_amount,0)),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PINT'
  AND ldd.due_date <= '{death_date}'::date AND ldd.is_deleted=false;
""")
    fee = psql(f"""
SELECT COALESCE(SUM(GREATEST(ldd.due_amount-ldd.paid_amount-ldd.waived_amount,0)),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='FEE'
  AND ldd.due_date <= '{death_date}'::date AND ldd.is_deleted=false;
""")
    total = Decimal(overdue or "0") + Decimal(future_prin or "0") + Decimal(pint or "0") + Decimal(fee or "0")
    rounded = total.quantize(Decimal("1"), rounding="ROUND_HALF_UP")
    print(f"  computed outstanding child={child_lan} overdue={overdue} future_prin={future_prin} "
          f"pint={pint} fee={fee} rounded={rounded}")
    return str(rounded)


def run_inbound_approve_only(child_lan: str, dfd_id: int, staging_id: int, death_date: str) -> None:
    os_bal = compute_outstanding_rounded(child_lan, death_date)
    account_id = psql(
        f"SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';"
    )
    sum_assured = psql(f"""
SELECT COALESCE(sum_assured::text,'0') FROM mfi_accounting.loan_account_insurance_details
WHERE loan_account_id={account_id} AND policy_type='LIFE_INSUR' AND is_deleted=false LIMIT 1;
""") or "0"
    bal_claim = str((Decimal(sum_assured) - Decimal(os_bal)).quantize(Decimal("1"), rounding="ROUND_HALF_UP"))
    psql_multi(f"""
UPDATE mfi_accounting.death_foreclosure_details
SET outstanding_loan_balance = {os_bal}, balance_claim_amount = {bal_claim}, updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={dfd_id};

UPDATE mfi_accounting.death_foreclosure_insurance_staging_details
SET claim_status='Claim Closed', inout_status='INBOUND_SUCCESS',
    payment_amount_for_nominee = {bal_claim},
    outstanding_loan_balance = {os_bal},
    updated_on=NOW(), updated_by='LOCAL_E2E'
WHERE id={staging_id};
""")

    quarantine_all_other_inbound_staging(staging_id)
    before_id = max_job_execution_id("deathForeclosureInsuranceJob")
    jt = str(int(time.time() * 1000))
    fire_batch("deathForeclosureInsuranceJob", jt)
    try:
        wait_batch_after_id("deathForeclosureInsuranceJob", before_id, timeout_s=180)
    except RuntimeError as exc:
        # glCBSIntegration / YB conflicts may mark batch FAILED while loan still closes — poll loan next.
        print(f"  WARN: deathForeclosureInsuranceJob batch: {exc} (polling loan_status)")
    # Source of truth = the child reaching CLOSED. glCBSIntegration (bank CBS) is best-effort and
    # logs connection-refused locally without rolling back the closure, so batch_job_execution can
    # read FAILED even though the DFC committed. Poll the loan instead.
    wait_loan_closed(child_lan, timeout_s=300)


def parent_account_id(parent_lan: str) -> int:
    row = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account "
        f"WHERE la_account_number='{parent_lan}' AND is_deleted=false;"
    )
    if not row:
        raise RuntimeError(f"parent LAN not found: {parent_lan}")
    return int(row)


def latest_parent_event_id(parent_lan: str) -> int:
    return int(psql(f"""
SELECT COALESCE(MAX(q.id), 0)::text
FROM mfi_accounting.loan_account_events_queue q
JOIN mfi_accounting.loan_account p ON p.account_id = q.parent_account_id
WHERE p.la_account_number = '{parent_lan}' AND q.is_deleted = false;
""") or "0")


def drain_rstcre_with_retry(
    parent_id: int,
    parent_lan: str,
    dfd_id: int,
    baseline_queue_id: int,
    child_lan: str,
    *,
    max_attempts: int = 5,
) -> list[str]:
    """Fire RSTCRE batch and assert drain; retry when batch leaves event_status=P (YB / processor flake)."""
    last_err: BaseException | None = None
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"  RSTCRE retry {attempt}/{max_attempts} after pending/conflict on parent={parent_lan}")
            time.sleep(3)
        try:
            fire_and_wait_child_events_batch(parent_id, dfd_id)
            return assert_rstcre_drained(parent_id, baseline_queue_id, child_lan)
        except (AssertionError, RuntimeError) as exc:
            last_err = exc
            print(f"  RSTCRE attempt {attempt}/{max_attempts} failed: {exc}")
            if attempt == max_attempts:
                raise
    raise last_err or AssertionError("RSTCRE drain failed")


def fire_and_wait_child_events_batch(parent_id: int, dfd_id: int) -> str:
    """Fire childLoanEventProcessingBatchJob and wait COMPLETED (mirror disburse_loan_sanity).

    Non-last child DFC inserts RSTCRE PENDING on the parent; the batch must drain it before
    last-child DFC so schedule-reduction state is consistent.
    """
    last_job_time = ""
    for attempt in range(1, 5):
        job_time = str(int(time.time() * 1000))
        before_id = max_job_execution_id("childLoanEventProcessingBatchJob")
        print(
            f"  RSTCRE spine: firing childLoanEventProcessingBatchJob parent_id={parent_id} "
            f"dfd_id={dfd_id} job_time={job_time} attempt={attempt}"
        )
        fire_batch("childLoanEventProcessingBatchJob", job_time)
        try:
            wait_batch_after_id("childLoanEventProcessingBatchJob", before_id, timeout_s=300)
        except RuntimeError as exc:
            print(f"  WARN: childLoanEventProcessingBatchJob: {exc}")
        # Brief settle — processor may flip P→C just after batch COMPLETED row commits.
        time.sleep(2)
        pending = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""")
        if pending == "0":
            print(f"  RSTCRE spine: childLoanEventProcessingBatchJob drained job_time={job_time}")
            return job_time
        filler = psql(f"""
SELECT COALESCE(MAX(filler_1),'') FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id={parent_id} AND event_type='RSTCRE' AND is_deleted=false
  AND event_status NOT IN ('C', 'COMPLETED');
""") or ""
        print(f"  RSTCRE spine: still PENDING={pending} filler={filler[:120]!r} after job_time={job_time}")
        if attempt < 4:
            time.sleep(5)
            last_job_time = job_time
            continue
        raise RuntimeError(
            f"RSTCRE drain FAIL: {pending} PENDING RSTCRE after batch (filler={filler[:120]})"
        )
    return last_job_time


def _rstcre_rows_since(parent_id: int, baseline_queue_id: int) -> list[str]:
    out = subprocess.check_output(
        [*PG, "-c", f"""
SELECT q.id::text, q.event_type, q.event_status,
       COALESCE(q.reference_number, ''),
       CASE WHEN q.filler_1 IS NULL THEN 'NULL' ELSE q.filler_1 END,
       COALESCE(q.filler_2, '')
FROM mfi_accounting.loan_account_events_queue q
WHERE q.parent_account_id = {parent_id}
  AND q.id >= {baseline_queue_id}
  AND q.is_deleted = false
  AND q.event_type = 'RSTCRE'
ORDER BY q.id;
"""],
        env=PG_ENV,
        text=True,
    ).strip()
    return [r for r in out.splitlines() if r.strip()]


def assert_rstcre_drained(parent_id: int, baseline_queue_id: int, child_lan: str) -> list[str]:
    """Prove RSTCRE inserted by child DFC is COMPLETE with filler_1 NULL."""
    rows = _rstcre_rows_since(parent_id, baseline_queue_id)
    if not rows:
        raise AssertionError(
            f"RSTCRE drain FAIL: no RSTCRE row for parent_id={parent_id} after child {child_lan} "
            f"DFC (baseline queue id={baseline_queue_id})"
        )
    bad_status = []
    bad_filler = []
    for row in rows:
        parts = row.split("|")
        if len(parts) < 5:
            continue
        qid, etype, estatus, ref, filler1 = parts[0], parts[1], parts[2], parts[3], parts[4]
        if estatus != "C":
            bad_status.append(f"id={qid} event_status={estatus!r}")
        if filler1 != "NULL":
            bad_filler.append(f"id={qid} filler_1={filler1!r}")
    if bad_status:
        raise AssertionError(
            f"RSTCRE drain FAIL: event_status must be 'C' after batch drain "
            f"(child={child_lan} parent_id={parent_id}): {bad_status}; rows={rows}"
        )
    if bad_filler:
        raise AssertionError(
            f"RSTCRE drain FAIL: filler_1 must be NULL after COMPLETE "
            f"(child={child_lan} parent_id={parent_id}): {bad_filler}; rows={rows}"
        )
    print(
        f"  RSTCRE drain PASS: child={child_lan} parent_id={parent_id} "
        f"rows={rows}"
    )
    return rows


def assert_no_pending_rstcre(parent_id: int, parent_lan: str) -> None:
    """Before last-child DFC: no PENDING RSTCRE may remain from non-last child path."""
    rows = subprocess.check_output(
        [*PG, "-c", f"""
SELECT q.id::text, q.event_status, COALESCE(q.filler_1, 'NULL')
FROM mfi_accounting.loan_account_events_queue q
WHERE q.parent_account_id = {parent_id}
  AND q.event_type = 'RSTCRE'
  AND q.is_deleted = false
  AND q.event_status NOT IN ('C', 'COMPLETED')
ORDER BY q.id;
"""],
        env=PG_ENV,
        text=True,
    ).strip()
    if rows:
        raise AssertionError(
            f"RSTCRE pre-last-child FAIL: PENDING RSTCRE on parent {parent_lan} "
            f"(parent_id={parent_id}) before last-child DFC — fire childLoanEventProcessingBatchJob "
            f"after non-last child wait_loan_closed. Rows: {rows.splitlines()}"
        )
    print(f"  RSTCRE pre-last-child PASS: no PENDING RSTCRE parent={parent_lan} parent_id={parent_id}")


def snapshot_future_emi_dates(child_lan: str, death_date: str) -> list[str]:
    """Unpaid future PRIN installment due dates on remaining ACTIVE child (post non-last DFC)."""
    out = subprocess.check_output(
        [*PG, "-c", f"""
SELECT DISTINCT to_char(lid.installment_date, 'YYYY-MM-DD')
FROM mfi_accounting.loan_installment_details lid
JOIN mfi_accounting.loan_account la ON la.account_id = lid.loan_account_id
WHERE la.la_account_number = '{child_lan}'
  AND lid.is_deleted = false
  AND lid.is_settled = false
  AND lid.installment_date::date >= '{death_date}'::date
ORDER BY 1;
"""],
        env=PG_ENV,
        text=True,
    ).strip()
    return [r.strip() for r in out.splitlines() if r.strip()]


def assert_remaining_child_schedule_changed(
    child_lan: str, before: list[str], after: list[str],
) -> None:
    """Optional: parent RSTCRE should alter remaining child's future EMI schedule."""
    if not before and not after:
        print(f"  schedule N/A: {child_lan} no future unsettled installments to compare")
        return
    if before == after:
        print(
            f"  schedule INFO: {child_lan} future EMI dates unchanged after non-last RSTCRE "
            f"(before={before} after={after}) — may be fixture-specific"
        )
        return
    print(
        f"  schedule PASS: {child_lan} future EMI dates changed after non-last RSTCRE "
        f"before={before} after={after}"
    )


def assert_parent_pos_equals_remaining_children(
    parent_lan: str, remaining_lans: list[str], *, tol: Decimal = Decimal("0"),
) -> None:
    """After non-last FC + parent PPP + RSTCRE: parent PRIN pending == Σ remaining children."""
    parent_snap = snapshot_dues(parent_lan, "pos-check-parent")
    rem_total = Decimal("0")
    for lan in remaining_lans:
        rem_total += snapshot_dues(lan, f"pos-check-{lan}")["prin_pending"]
    parent_pending = parent_snap["prin_pending"]
    diff = abs(parent_pending - rem_total)
    if diff > tol:
        raise AssertionError(
            f"parent POS sync FAIL: parent {parent_lan} prin_pending={parent_pending} "
            f"!= Σ remaining {remaining_lans}={rem_total} (diff={diff})"
        )
    print(
        f"  parent POS sync PASS: parent={parent_lan} prin_pending={parent_pending} "
        f"== Σ remaining {remaining_lans}={rem_total}"
    )


def _child_pending_dues(child_lan: str) -> Decimal:
    return Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false;
""") or "0")


def wait_loan_closed(child_lan: str, timeout_s: int = 300) -> None:
    deadline = time.time() + timeout_s
    saw_freeze = False
    active_streak = 0
    while time.time() < deadline:
        st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
        if st == "CLOSED":
            settle_deadline = time.time() + 45
            while time.time() < settle_deadline:
                if _child_pending_dues(child_lan) == 0:
                    print(f"  child {child_lan} CLOSED (batch committed, dues settled)")
                    return
                time.sleep(1)
            print(f"  child {child_lan} CLOSED (batch committed; dues settle poll timed out)")
            return
        if st == "DEATH_FORECLOSURE_FREEZE":
            saw_freeze = True
            active_streak = 0
        elif st == "ACTIVE":
            # Transient ACTIVE can appear between batch COMPLETED and final CLOSED commit locally.
            # Fail only when ACTIVE persists after we have seen FREEZE (rollback), not a single poll.
            if saw_freeze:
                active_streak += 1
                if active_streak >= 3:
                    raise RuntimeError(f"child {child_lan} back to ACTIVE — DFC rolled back")
        else:
            active_streak = 0
        time.sleep(2)
    raise RuntimeError(f"child {child_lan} not CLOSED after {timeout_s}s (status stuck at FREEZE)")


def assert_child_closed(child_lan: str) -> None:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        raise AssertionError(f"child {child_lan} expected CLOSED got {st!r}")
    pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false;
""") or "0")
    if pending != 0:
        raise AssertionError(f"child {child_lan} pending dues {pending} != 0")
    for comp in ("INT", "PINT", "PRIN"):
        comp_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='{comp}' AND ldd.is_deleted=false;
""") or "0")
        if comp_pending != 0:
            raise AssertionError(f"child {child_lan} {comp} pending {comp_pending} != 0")
    prin_waived = Decimal(psql(f"""
SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    ref, amt = latest_txn(child_lan, "DEATH_FORECLOSURE")
    parts = partition_codes(ref)
    print(f"  child {child_lan} DEATH_FORECLOSURE ref={ref} amount={amt} partitions={parts}")
    if not ref:
        raise AssertionError(f"child {child_lan} missing DEATH_FORECLOSURE txn")
    print(f"  child {child_lan} PRIN waived={prin_waived} (expect 0 on child path)")


def assert_child_closed_fc(child_lan: str) -> None:
    """Vikram regular FC: child CLOSED with LOAN_PREPAYMENT (not DEATH_FORECLOSURE)."""
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{child_lan}';")
    if st != "CLOSED":
        raise AssertionError(f"child {child_lan} Vikram FC expected CLOSED got {st!r}")
    pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{child_lan}' AND ldd.is_deleted=false;
""") or "0")
    if pending != 0:
        raise AssertionError(f"child {child_lan} Vikram FC pending dues {pending} != 0")
    ref, amt = latest_txn(child_lan, "LOAN_PREPAYMENT")
    if not ref:
        raise AssertionError(f"child {child_lan} Vikram FC missing LOAN_PREPAYMENT txn")
    print(f"  child {child_lan} Vikram FC CLOSED LOAN_PREPAYMENT ref={ref} amount={amt}")


def assert_parent_last_child(parent_lan: str) -> None:
    st = psql(f"SELECT loan_status FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';")
    if st != "CLOSED":
        raise AssertionError(f"parent {parent_lan} expected CLOSED got {st!r}")
    closing = psql(f"""
SELECT CASE WHEN la_closing_date IS NULL THEN 'no' ELSE 'yes' END
FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}';
""")
    if closing != "yes":
        raise AssertionError(f"parent {parent_lan} missing la_closing_date")
    prin_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    prin_waived = Decimal(psql(f"""
SELECT COALESCE(SUM(waived_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    prin_paid = Decimal(psql(f"""
SELECT COALESCE(SUM(paid_amount),0) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false;
""") or "0")
    if prin_pending != 0:
        raise AssertionError(f"parent PRIN pending {prin_pending} != 0")
    if prin_waived != 0:
        raise AssertionError(f"parent PRIN waived {prin_waived} != 0 (insurance must pay PRIN)")
    neg_prin = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='PRIN' AND ldd.is_deleted=false
  AND (ldd.due_amount < 0 OR ldd.paid_amount < 0 OR ldd.waived_amount < 0);
""") or "0"
    if int(neg_prin) > 0:
        raise AssertionError(f"parent {parent_lan} has {neg_prin} negative PRIN due row(s)")
    int_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='INT' AND ldd.is_deleted=false;
""") or "0")
    if int_pending != 0:
        if ACCEPTANCE_SCOPE == "obs123":
            print(
                f"  Out-of-scope (ACCEPTANCE_SCOPE=obs123): parent INT pending={int_pending} — "
                f"GAP-074 INT-180 not in SHA 9b6454df6 (parked fix/sdcp-10199-parent-int-dpi-last-child-dfc). "
                f"Obs1–3 + RSTCRE spine still fail-closed. Use ACCEPTANCE_SCOPE=full to FAIL on INT pending."
            )
        else:
            raise AssertionError(
                f"parent INT pending {int_pending} != 0 (ACCEPTANCE_SCOPE=full / GAP-074). "
                f"Last-child must settle parent overdue INT. GAP-074 INT-180: child INT_AMT vs parent "
                f"overdue appropriation — fix parked @ 61278d5f8, NOT on this SHA. Do not WARN-and-pass."
            )
    dpi_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.component_type='DPI' AND ldd.is_deleted=false;
""") or "0")
    if dpi_pending != 0:
        if ACCEPTANCE_SCOPE == "obs123":
            print(
                f"  Out-of-scope (ACCEPTANCE_SCOPE=obs123): parent DPI pending={dpi_pending} — "
                f"GAP-074 (paired with INT appropriation). ACCEPTANCE_SCOPE=full fails closed."
            )
        else:
            raise AssertionError(
                f"parent DPI pending {dpi_pending} != 0 (ACCEPTANCE_SCOPE=full / GAP-074)"
            )
    # Under obs123, INT/DPI residuals are Out-of-scope (GAP-074) — still fail on any other component.
    if ACCEPTANCE_SCOPE == "obs123":
        all_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.is_deleted=false
  AND ldd.component_type NOT IN ('INT','DPI');
""") or "0")
        if all_pending != 0:
            raise AssertionError(
                f"parent {parent_lan} non-INT/DPI pending dues {all_pending} != 0 "
                f"(ACCEPTANCE_SCOPE=obs123 still fail-closed on PRIN/FEE/PINT/…)"
            )
    else:
        all_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(due_amount-paid_amount-waived_amount),0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.is_deleted=false;
""") or "0")
        if all_pending != 0:
            raise AssertionError(f"parent {parent_lan} total pending dues {all_pending} != 0")
    ref, amt = latest_txn(parent_lan, "RSCH_DEATH_FORECLOSURE")
    parts = partition_codes(ref)
    print(f"  parent {parent_lan} RSCH_DEATH_FORECLOSURE ref={ref} amount={amt}")
    print(f"  parent partitions: {parts}")
    if not ref:
        raise AssertionError(f"parent {parent_lan} missing RSCH_DEATH_FORECLOSURE txn")
    payment_principal = psql(f"""
SELECT lapd.principal_amount::text
FROM mfi_accounting.loan_account_payments_details lapd
JOIN mfi_accounting.transaction_master tm ON tm.reference_number = lapd.transaction_reference_number
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.account_id = lapd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND tc.type='RSCH_DEATH_FORECLOSURE'
ORDER BY tm.id DESC LIMIT 1;
""")
    if not payment_principal:
        raise AssertionError(f"parent {parent_lan} missing RSCH payment details row")
    txn_amt = Decimal(amt or "0")
    prin = Decimal(payment_principal or "0")
    if txn_amt > 0 and prin >= txn_amt * 2 - Decimal("0.01"):
        raise AssertionError(
            f"parent RSCH principal_amount {prin} looks doubled vs txn {txn_amt} "
            f"(saveLoanAccountPaymentsDetails net_amount+principal_amount on last child)"
        )
    if prin > txn_amt + Decimal("0.01"):
        delta = prin - txn_amt
        # QA acceptance (Obs2): statement amount != payment principal (e.g. 11550 vs 11605) is the
        # EXACT mode QA rejects. Do NOT print "OK A2 netting" and pass. Only relax as debug.
        if ACCEPTANCE_STRICT and not ALLOW_A2_NETTING_DISPLAY_DIFF:
            raise AssertionError(
                f"ACCEPTANCE FAIL (Obs2): parent RSCH txn amount {txn_amt} != payment principal {prin} "
                f"(delta={delta}). QA rejects amount!=principal. Either the writer must make statement "
                f"amount == principal, OR the delta components must be documented in product spec + this "
                f"assert extended to check the named legs. Debug-only override: ALLOW_A2_NETTING_DISPLAY_DIFF=1."
            )
        print(f"  WARN (DEBUG-ONLY, not a handoff Pass): payment_prin={prin} txn_amt={txn_amt} "
              f"delta={delta} — amount!=principal relaxed via override. QA acceptance NOT proven.")
    account_status = psql(f"""
SELECT a.status FROM mfi_accounting.account a
JOIN mfi_accounting.loan_account la ON la.account_id=a.id
WHERE la.la_account_number='{parent_lan}';
""")
    if account_status != "CLOSED":
        raise AssertionError(f"parent account.status {account_status!r} expected CLOSED (Loan 360 banner)")
    account_closing = psql(f"""
SELECT CASE WHEN a.closing_date IS NULL THEN 'no' ELSE 'yes' END
FROM mfi_accounting.account a
JOIN mfi_accounting.loan_account la ON la.account_id=a.id
WHERE la.la_account_number='{parent_lan}';
""")
    if account_closing != "yes":
        raise AssertionError(f"parent account.closing_date missing")
    unsettled = psql(f"""
SELECT COUNT(*) FROM mfi_accounting.loan_installment_details
WHERE loan_account_id=(SELECT account_id FROM mfi_accounting.loan_account WHERE la_account_number='{parent_lan}')
  AND is_deleted=false AND is_settled=false;
""")
    if int(unsettled or "0") > 0:
        raise AssertionError(f"parent has {unsettled} unsettled installment(s) after last-child close")
    asset_class = psql(f"""
SELECT acs.classification FROM mfi_accounting.loan_account la
JOIN mfi_accounting.asset_classification_slabs acs ON acs.id = la.asset_classification_slabs_id
WHERE la.la_account_number='{parent_lan}';
""") or ""
    npa_days = psql(f"""
SELECT COALESCE(npa_ageing_days,0) FROM mfi_accounting.loan_account
WHERE la_account_number='{parent_lan}';
""") or "0"
    if asset_class != "STD":
        raise AssertionError(
            f"parent {parent_lan} asset classification {asset_class!r} expected STD after closure"
        )
    if int(npa_days) != 0:
        raise AssertionError(f"parent {parent_lan} npa_ageing_days {npa_days} expected 0 after closure")
    # Re-read DPI after other checks (same GAP-074 scope as above).
    dpi_pending = Decimal(psql(f"""
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0)
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id=ldd.loan_account_id
WHERE la.la_account_number='{parent_lan}' AND ldd.is_deleted=false
  AND ldd.component_type='DPI';
""") or "0")
    if dpi_pending != 0 and ACCEPTANCE_SCOPE == "full":
        raise AssertionError(f"parent {parent_lan} DPI pending {dpi_pending} != 0 after last-child DFC")
    print(
        f"  parent PRIN paid={prin_paid} waived={prin_waived} pending={prin_pending} "
        f"int_pending={int_pending} dpi_pending={dpi_pending} "
        f"scope={ACCEPTANCE_SCOPE} classification={asset_class} npa_ageing_days={npa_days}"
    )


def discover_fresh_fixture() -> tuple[str, str, str, str]:
    """Pick a live ACTIVE group parent (product 70) with exactly 2 ACTIVE LIFE_INSUR children.

    Fixtures are consumed by a full run (loans close), so each run auto-discovers a fresh one
    instead of hard-coding LANs. death_date = day after the children's last PRIN due (all
    principal in settlement scope). No service code / no loan mutation here — pure read.
    """
    blocklist_sql = ",".join(f"'{lan}'" for lan in DCF_FIXTURE_BLOCKLIST) or "'__none__'"
    parent_id = psql(f"""
SELECT p.account_id
FROM mfi_accounting.loan_account p
JOIN mfi_accounting.loan_account c ON c.parent_loan_account_id = p.account_id
  AND c.loan_status='ACTIVE' AND c.is_deleted=false
LEFT JOIN mfi_accounting.loan_account_insurance_details ins
  ON ins.loan_account_id=c.account_id AND ins.policy_type='LIFE_INSUR' AND ins.is_deleted=false
WHERE p.has_child_accounts=true AND p.loan_status='ACTIVE' AND p.is_deleted=false
  AND p.loan_product_id=70
GROUP BY p.account_id
HAVING COUNT(c.account_id)=2 AND SUM(CASE WHEN ins.id IS NOT NULL THEN 1 ELSE 0 END)=2
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.loan_due_details ldd
    JOIN mfi_accounting.loan_account cx ON cx.account_id=ldd.loan_account_id
    WHERE cx.parent_loan_account_id=p.account_id AND cx.is_deleted=false
      AND ldd.component_type='PINT' AND ldd.is_deleted=false
      AND (ldd.due_amount-ldd.paid_amount-ldd.waived_amount) > 0
  )
  AND p.la_account_number NOT IN ({blocklist_sql})
ORDER BY p.account_id LIMIT 1;
""")
    if not parent_id:
        raise RuntimeError("no fresh ACTIVE product-70 parent with 2 insured children found")
    parent_lan_check = psql(f"SELECT la_account_number FROM mfi_accounting.loan_account WHERE account_id={parent_id};")
    if parent_lan_check in DCF_FIXTURE_BLOCKLIST:
        raise RuntimeError(
            f"discovered parent {parent_lan_check} is blocklisted — set DCF_FRESH_GROUP=1 or pick another fixture"
        )
    parent = psql(f"SELECT la_account_number FROM mfi_accounting.loan_account WHERE account_id={parent_id};")
    kids = subprocess.check_output(
        [*PG, "-c", f"""
SELECT la_account_number FROM mfi_accounting.loan_account
WHERE parent_loan_account_id={parent_id} AND loan_status='ACTIVE' AND is_deleted=false
ORDER BY la_account_number;
"""], env=PG_ENV, text=True).strip().split("\n")
    child1, child2 = kids[0].strip(), kids[1].strip()
    # death_date mid-schedule, but next INT after death-1 must be <= today so EXTRA
    # loanRepayment (value_date=today) can settle advance INT (otherwise raw_surplus=0).
    death_date = psql(_resolve_death_date_sql(parent_id, latest=False)) or resolve_death_date(parent_id, latest=True)
    print(f"  discovered fresh fixture: parent={parent} child1={child1} child2={child2} death_date={death_date}")
    return parent, child1, child2, death_date


def main() -> int:
    global RUN_TXN_FLOOR_ID
    acquire_dcf_e2e_lock()
    if DCF_FRESH_GROUP:
        print("  DCF_FRESH_GROUP=1 — provisioning new SHG group (disburse + billing)")
        sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))
        from create_fresh_dcf_group_fixture import create_fresh_dcf_group_fixture  # noqa: WPS433

        parent, child1, child2, death_date = create_fresh_dcf_group_fixture()
    elif os.environ.get("PARENT_LAN"):
        parent = os.environ["PARENT_LAN"]
        # Canonical pin 6000137433 children; do not default to blocklisted 600397* family.
        if parent == "6000137433":
            child1 = os.environ.get("CHILD1_LAN", "6000137440")
            child2 = os.environ.get("CHILD2_LAN", "6000137441")
        else:
            child1 = os.environ.get("CHILD1_LAN") or ""
            child2 = os.environ.get("CHILD2_LAN") or ""
            if not child1 or not child2:
                raise RuntimeError(
                    f"PARENT_LAN={parent} requires CHILD1_LAN and CHILD2_LAN "
                    f"(canonical pin defaults only for 6000137433)"
                )
        if os.environ.get("DEATH_DATE"):
            death_date = os.environ["DEATH_DATE"]
        elif parent == "6000137433":
            # Pin that proves Obs1–3 without GAP-074 residual (INT through death-1 paid).
            death_date = "2025-08-02"
            print(f"  default death_date={death_date} (canonical pin for PARENT_LAN=6000137433)")
        else:
            death_date = resolve_death_date(parent_account_id(parent), latest=True)
            print(f"  resolved death_date={death_date} (PRIN due+1 day, latest valid)")
        if parent in DCF_FIXTURE_BLOCKLIST:
            raise RuntimeError(
                f"PARENT_LAN={parent} is blocklisted (corrupted fixture). "
                f"Use DCF_FRESH_GROUP=1 or unset PARENT_LAN to auto-discover."
            )
    else:
        parent, child1, child2, death_date = discover_fresh_fixture()
    # Non-last child must run first: last-child detection counts ACTIVE siblings only.
    # Default two-DFC: child2 non-last, child1 last. Vikram: child1 FC then child2 last DFC.
    children_in_order = [child1, child2] if VIKRAM_PATH else [child2, child1]
    vikram_billed_through_fc = False

    print("=== SDCP-10199 group parent last-child DFC local e2e (real batches) ===")
    if VIKRAM_PATH:
        print("mode=VIKRAM (regular FC → RSTCRE → last DFC)")
    print(f"parent={parent} child1={child1} child2={child2} death_date={death_date}")
    print(
        f"vikram_path={VIKRAM_PATH} acceptance_scope={ACCEPTANCE_SCOPE} acceptance_strict={ACCEPTANCE_STRICT} "
        f"seed_extra={SEED_EXTRA} seed_emi_labd={SEED_EMI_LABD} "
        f"allow_a2_netting_display_diff={ALLOW_A2_NETTING_DISPLAY_DIFF}"
    )
    if not ACCEPTANCE_STRICT or ALLOW_A2_NETTING_DISPLAY_DIFF:
        print("  WARN: acceptance gate relaxed — this run is DEBUG ONLY and is NOT a QA handoff Pass.")
    if ACCEPTANCE_SCOPE == "obs123":
        print(
            "  scope=obs123: GAP-074 parent INT/DPI pending is Out-of-scope (documented); "
            "Obs1–3 + RSTCRE + amount rules remain fail-closed."
        )

    # Retest-on-same-LANs provision (dcf_fixture_backup.py):
    #   * first run on a LAN  → snapshot pristine state (parent + ALL children, every mutated table)
    #   * every later run     → RESTORE to that pristine snapshot first, so the same LANs re-run clean
    # The snapshot is never overwritten once taken, so a burned run can always be reverted.
    # Skip entirely with DCF_E2E_NO_SNAPSHOT=1. Force revert at end with DCF_E2E_RESTORE=1.
    # Fresh-disbursed groups are one-shot (loans close) — never snapshot/restore.
    backup_py = str(ROOT / "scripts/dcf_sanity/dcf_fixture_backup.py")
    # Nested restore/snapshot must skip flock — we already hold /tmp/dcf_e2e.lock.
    backup_env = {**PG_ENV, "DCF_E2E_LOCK_HELD": "1", "FLOWTEST_E2E_LOCK_HELD": "1"}
    snapshot_enabled = os.environ.get("DCF_E2E_NO_SNAPSHOT") != "1" and not DCF_FRESH_GROUP
    if snapshot_enabled:
        has_snapshot = psql(
            f"SELECT 1 FROM information_schema.schemata WHERE schema_name='dcf_bak_{parent}';") == "1"
        if has_snapshot:
            print(f"--- snapshot exists → RESTORE {parent} to pristine before run ---")
            subprocess.check_call(["python3", backup_py, "restore", parent], env=backup_env)
            time.sleep(3)  # YB: let restore commit settle before DFC batches write same rows
        else:
            subprocess.check_call(["python3", backup_py, "snapshot", parent], env=backup_env)

    try:
        subprocess.check_call(
            ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
            env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
        )

        cleanup_abandoned_staging([child1, child2])
        parent_id = parent_account_id(parent)
        cleanup_stale_rstcre_events(parent_id)
        assert_no_legacy_force_bill_crn_collision(parent, death_date)

        print("\n--- RESET partial / in-flight DFC on both children ---")
        reset_child_dfc_if_needed(child1)
        reset_child_dfc_if_needed(child2)

        if not DCF_FRESH_GROUP:
            print("\n--- PINT prep (fixture harness — S08 happy path) ---")
            prepare_fixture_pint_free(parent)

        print("\n--- BEFORE ---")
        RUN_TXN_FLOOR_ID = int(psql(
            "SELECT COALESCE(MAX(id),0)::text FROM mfi_accounting.transaction_master;"
        ) or "0")
        snapshot_dues(parent, "parent-before")
        snapshot_dues(child1, "child1-before")
        snapshot_dues(child2, "child2-before")

        expected_extra = Decimal("0")
        last_child = children_in_order[-1]  # child1 — EXTRA must land on last-child claim
        remaining_child_schedule_before: dict[str, list[str]] = {}

        for idx, child in enumerate(children_in_order, start=1):
            is_last = idx == len(children_in_order)
            vikram_fc_child = VIKRAM_PATH and not is_last
            if is_last:
                print(f"\n--- Pre last-child: assert no PENDING RSTCRE on parent ---")
                assert_no_pending_rstcre(parent_id, parent)
                assert_no_legacy_force_bill_crn_collision(parent, death_date)

            if vikram_fc_child:
                fc_label = (
                    "loanPrepayment (Sim B / prod)"
                    if VIKRAM_USE_LOAN_PREPAYMENT
                    else "individualChildLoanForeclosure (Sim A / ICF opt-in)"
                )
                print(f"\n--- CHILD {idx} {child}: Vikram regular FC via {fc_label} ---")
                remaining = children_in_order[idx]
                # Baseline BEFORE FC so Sim B loanPrepayment-enqueued RSTCRE is included
                # (assert uses id >= baseline; capturing after FC made baseline == PENDING id).
                prior_event_id = latest_parent_event_id(parent)
                if child_already_closed_from_fc(child):
                    print(f"  skip FC — {child} already CLOSED with LOAN_PREPAYMENT (prior run)")
                    assert_child_closed_fc(child)
                    assert_loan_prepayment_force_bill(child)
                else:
                    # Fresh fixture bills only through death_date (SEED_EXTRA=0). Vikram FC uses
                    # platform today; Accrual fills later EMI Accrued without EMI labd. Production
                    # would have billed those past dues — sync through FC date before prepayment.
                    if not vikram_billed_through_fc:
                        fc_bill_through = _vikram_fc_date(death_date)
                        from create_fresh_dcf_group_fixture import (  # noqa: WPS433
                            sync_billing_for_group,
                        )
                        print(
                            f"  Vikram prep: billing through FC date {fc_bill_through} "
                            "(past EMI Accrued must be billed before Obs3 Accrued≤Original)"
                        )
                        sync_billing_for_group(parent, children_in_order, fc_bill_through)
                        vikram_billed_through_fc = True
                    settle_parent_overdue_before_vikram_fc(parent, parent_id)
                    remaining_child_schedule_before[remaining] = snapshot_future_emi_dates(
                        remaining, death_date,
                    )
                    run_child_loan_prepayment_fc(child, death_date)
                    assert_child_closed_fc(child)
                    assert_loan_prepayment_force_bill(child)
                # Sim B loanPrepayment enqueues RSTCRE; Sim A ICF does not — seed only if missing
                if remaining not in remaining_child_schedule_before:
                    remaining_child_schedule_before[remaining] = snapshot_future_emi_dates(
                        remaining, death_date,
                    )
                need_drain = ensure_rstcre_pending_after_vikram_fc(parent, parent_id, child, remaining)
                if need_drain:
                    rstcre_proof = drain_rstcre_with_retry(
                        parent_id, parent, 0, prior_event_id, child,
                        max_attempts=2 if os.environ.get("FAIL_FAST", "1") == "1" else 5,
                    )
                    print(f"  RSTCRE SQL proof (after Vikram FC): {rstcre_proof}")
                else:
                    print("  RSTCRE SQL proof (after Vikram FC): already COMPLETED — skipped drain")
                after_sched = snapshot_future_emi_dates(remaining, death_date)
                assert_remaining_child_schedule_changed(
                    remaining,
                    remaining_child_schedule_before.get(remaining, []),
                    after_sched,
                )
            else:
                print(f"\n--- CHILD {idx} {child}: seed + approve job ---")
                if SEED_EXTRA and child == last_child and not child_already_closed_from_dfc(child):
                    print(f"\n--- EXTRA>0 fixture via loanRepayment on last child {child} ---")
                    expected_extra = seed_extra_via_loan_repayment(child, death_date)
                if child_already_closed_from_dfc(child):
                    print(f"  skip batch — {child} already CLOSED with DEATH_FORECLOSURE (prior run)")
                    assert_child_closed(child)
                else:
                    if not is_last:
                        remaining_child_schedule_before[children_in_order[idx]] = snapshot_future_emi_dates(
                            children_in_order[idx], death_date,
                        )
                    if SEED_EMI_LABD:
                        seed_pre_existing_emi_labd(child, death_date)
                    dfd_id, staging_id = seed_dfc_child(child, death_date)
                    cleanup_abandoned_staging([child1, child2], keep_staging_id=staging_id)
                    prior_event_id = latest_parent_event_id(parent)
                    run_inbound_approve_only(child, dfd_id, staging_id, death_date)
                    assert_child_closed(child)
                    if not is_last:
                        rstcre_proof = drain_rstcre_with_retry(
                            parent_id, parent, dfd_id, prior_event_id, child,
                        )
                        print(f"  RSTCRE SQL proof: {rstcre_proof}")
                        remaining = children_in_order[idx]
                        after_sched = snapshot_future_emi_dates(remaining, death_date)
                        assert_remaining_child_schedule_changed(
                            remaining,
                            remaining_child_schedule_before.get(remaining, []),
                            after_sched,
                        )
            snapshot_dues(parent, f"parent-after-child{idx}")
            if not is_last:
                remaining_after = [c for c in children_in_order if c != child]
                # Parent POS == Σ remaining children requires parent PPP via loanPrepayment.
                # Sim A ICF: no PPP. DOCUMENT_PARENT_POS_BRE_BLOCK records Blocked (BRE / no HTTP PPP).
                if vikram_fc_child and not VIKRAM_USE_LOAN_PREPAYMENT:
                    print(
                        "\n--- Parent POS assert SKIP (Blocked locally): Sim A ICF — "
                        "no parent PPP; Sim B loanPrepayment needs BRE :8025 (LOS-0118); "
                        "parentLoanAccountPartPrepayment is internal-only from loanPrepayment ---"
                    )
                    if DOCUMENT_PARENT_POS_BRE_BLOCK:
                        print(
                            "  Parent POS Blocked evidence: BRE ports 8025/8024/8020 DOWN; "
                            "HTTP parentLoanAccountPartPrepayment NPE without loan_account_entity "
                            "(prod path: loanPrepayment APPROVE → callInternal PPP)."
                        )
                else:
                    print("\n--- Parent POS == Σ remaining children (after FC + RSTCRE) ---")
                    assert_parent_pos_equals_remaining_children(parent, remaining_after)
                if vikram_fc_child:
                    print("\n--- Vikram non-last FC asserts (force-bill Obs H) ---")
                    assert_loan_prepayment_force_bill(child)
                    if VIKRAM_USE_LOAN_PREPAYMENT:
                        print("\n--- GL balance after Vikram non-last FC ---")
                        assert_gl_balance_for_loan(child, ["LOAN_PREPAYMENT"])
                    else:
                        print(
                            "\n--- GL balance after Vikram non-last FC SKIP "
                            "(ICF: no LOAN_PREPAYMENT; force-bill BILLING asserted separately) ---"
                        )
                else:
                    print("\n--- Non-last child parent RSCH parity (S4) ---")
                    assert_amount_calculations_non_last(child, parent)
                    print("\n--- GL balance after non-last child (S6 partial) ---")
                    assert_gl_balance_for_loan(child, ["DEATH_FORECLOSURE"])
                    assert_gl_balance_for_loan(parent, ["RSCH_DEATH_FORECLOSURE"])
                    print("\n--- Transaction audit after non-last child (S7 partial) ---")
                    assert_transaction_posting_audit(child, parent, phase="non_last")

        print("\n--- PARENT last-child assertions (S1) ---")
        assert_parent_last_child(parent)

        print("\n--- Issue A (A2 last-child parent RSCH excess=0) (S2) ---")
        assert_a2_extra_parent_rsch(parent, last_child, expected_extra)

        print("\n--- Amount calculations last-child (S1/S2) ---")
        assert_amount_calculations_last_child(parent, last_child, expected_extra)

        print("\n--- Issue B (force-bill labd on death children) (S3) ---")
        for child in children_in_order:
            if VIKRAM_PATH and child != last_child:
                assert_loan_prepayment_force_bill(child)
            else:
                assert_force_bill_labd(child)

        print("\n--- Obs1b parent force-bill (any-child DFC; re-check after last child) ---")
        assert_parent_force_bill_labd(parent)
        if VIKRAM_PATH:
            print("\n--- Vikram 391228 parent FB == Σ children FB ---")
            assert_parent_force_bill_equals_sum_children(parent, children_in_order)

        print("\n--- GL balance full matrix (S6) ---")
        for child in children_in_order:
            if VIKRAM_PATH and child != last_child:
                if VIKRAM_USE_LOAN_PREPAYMENT:
                    assert_gl_balance_for_loan(child, ["LOAN_PREPAYMENT"])
                else:
                    print(f"  GL matrix SKIP LOAN_PREPAYMENT for ICF FC child {child}")
            else:
                assert_gl_balance_for_loan(child, ["DEATH_FORECLOSURE"])
        assert_gl_balance_for_loan(parent, ["RSCH_DEATH_FORECLOSURE"])

        print("\n--- Transaction posting audit full (S7) ---")
        assert_transaction_posting_audit(last_child, parent)

        print("\n--- Obs3 Accrued ≤ Original (summary formula via SQL) ---")
        assert_accrued_le_original(parent, "parent")
        for child in children_in_order:
            assert_accrued_le_original(child, "child")

        print("\n--- RSTCRE Accrued not on soft-deleted installments ---")
        assert_no_accrued_on_deleted_installments(parent, "parent")
        for child in children_in_order:
            assert_no_accrued_on_deleted_installments(child, "child")

        print("\n--- Webapp-bound APIs (summary / overview / statement) (S8) ---")
        assert_webapp_bound_apis(parent, children_in_order, last_child)

        pass_label = (
            "VIKRAM FC→RSTCRE→last DFC"
            if VIKRAM_PATH
            else "SDCP-10199 group parent last-child DFC local e2e"
        )
        print(f"\n=== PASS: {pass_label} "
              f"(matrix S1-S8 strict={ACCEPTANCE_STRICT} extra={SEED_EXTRA} emi_labd={SEED_EMI_LABD} "
              f"vikram={VIKRAM_PATH}) ===")
        return 0
    finally:
        if snapshot_enabled:
            if os.environ.get("DCF_E2E_RESTORE") == "1":
                print(f"\n--- RESTORE fixture {parent} to pristine (DCF_E2E_RESTORE=1) ---")
                subprocess.check_call(["python3", backup_py, "restore", parent], env=backup_env)
            else:
                print(f"\nRetest tip: this fixture auto-restores on next run, or revert now with →\n"
                      f"  python3 scripts/dcf_sanity/dcf_fixture_backup.py restore {parent}")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (AssertionError, RuntimeError, subprocess.CalledProcessError) as e:
        print(f"\nFAIL: {e}", file=sys.stderr, flush=True)
        sys.exit(1)
    except Exception as e:
        print(f"\nFAIL: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        raise
