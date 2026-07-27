#!/usr/bin/env python3
"""TRUE-TO-WORLD R0 proofs for universal invariants.

  proof_ii  — mutate one partition amount → invariants MUST FAIL (then restore)
  proof_iii — seed BPI_AMT AIR credit (txn stays per-txn balanced) → MUST FAIL 392164

Usage:
  python3 scripts/testing/flowtest/r0_invariant_proofs.py ii
  python3 scripts/testing/flowtest/r0_invariant_proofs.py iii --lan <LAN>
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from flowtest.db import psql, psql_multi  # noqa: E402
from flowtest.invariants import (  # noqa: E402
    bpi_air_credit_after_force_bill,
    run_universal_invariants,
    snapshot_invariants,
)

PROBE_TAG = "R0_INVARIANT_PROBE"


def _pick_lan(preferred: str | None) -> str:
    if preferred:
        return preferred
    lan = psql(
        """
SELECT td.account_number
FROM mfi_accounting.transaction_details td
JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_id
  AND tm.reversed = false AND tm.status = 'SUCCESS'
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
WHERE td.account_number ~ '^[0-9]{10}$'
GROUP BY td.account_number
HAVING COUNT(DISTINCT tm.id) >= 1
ORDER BY MAX(tm.id) DESC
LIMIT 1;
"""
    )
    if not lan:
        raise RuntimeError("no LAN with SUCCESS txn for probe")
    return lan.strip()


def proof_ii(lan: str) -> int:
    """Break per-txn D=C by bumping one debit amount; invariants must FAIL."""
    print(f"=== R0 proof_ii deliberate GL imbalance lan={lan} ===")
    baseline = snapshot_invariants([lan])
    row = psql(
        f"""
SELECT tpd.id::text||'|'||tpd.amount::text||'|'||tm.reference_number
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
  AND tm.reversed = false AND tm.status = 'SUCCESS'
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{lan}' AND tpd.cr_dr_indicator = 'D'
ORDER BY tpd.id DESC LIMIT 1;
"""
    )
    if not row:
        print("FAIL: proof_ii no debit partition to mutate")
        return 1
    pid, amt, ref = row.split("|", 2)
    print(f"  mutating partition id={pid} ref={ref} amount {amt} → +15")
    psql_multi(
        f"""
UPDATE mfi_accounting.transaction_partition_details
SET amount = amount + 15.000000,
    source_amount = COALESCE(source_amount, amount) + 15.000000
WHERE id = {pid};
"""
    )
    try:
        run_universal_invariants([lan], baseline=baseline, label="proof_ii")
        print("FAIL: proof_ii expected invariants to FAIL but they PASSED")
        return 1
    except AssertionError as exc:
        print(f"PASS: proof_ii caught imbalance: {exc}")
        return 0
    finally:
        psql_multi(
            f"""
UPDATE mfi_accounting.transaction_partition_details
SET amount = {amt}::numeric,
    source_amount = {amt}::numeric
WHERE id = {pid};
"""
        )
        print(f"  restored partition id={pid} amount={amt}")


def _ensure_synthetic_loan_prepayment(lan: str, aid: str) -> tuple[str, str | None]:
    """Insert probe LOAN_PREPAYMENT SUCCESS txn if none exists; return (tm_id, ref)."""
    lp_tid = psql(
        f"""
SELECT tm.id::text
FROM mfi_accounting.transaction_details td
JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_id
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE td.account_number = '{lan}' AND tc.type = 'LOAN_PREPAYMENT'
  AND tm.reversed = false AND tm.status = 'SUCCESS'
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    if lp_tid:
        ref = psql(f"SELECT reference_number FROM mfi_accounting.transaction_master WHERE id={lp_tid};")
        return lp_tid.strip(), ref.strip() if ref else None

    cat_id = psql(
        "SELECT id::text FROM mfi_accounting.transaction_catalogue "
        "WHERE type='LOAN_PREPAYMENT' ORDER BY id LIMIT 1;"
    )
    if not cat_id:
        raise RuntimeError("no LOAN_PREPAYMENT catalogue row")
    ref = f"R0LP{int(time.time() * 1000)}"
    stan = f"r0lp-{ref[-12:]}"
    office = "1"
    tmpl = psql(
        f"""
SELECT COALESCE(tpd.currency,'INR'), COALESCE(tpd.account_number,'CG13578')
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_details td ON td.transaction_id=tpd.transaction_id
WHERE td.account_number='{lan}' LIMIT 1;
"""
    )
    currency, gl_acct = (tmpl or "INR|CG13578").split("|", 1)
    td_tmpl = psql(
        f"""
SELECT COALESCE(originating_office_id,1)::text, COALESCE(office_id,1)::text,
       COALESCE(gl_code,'CG13334'), COALESCE(business_date::text, NOW()::text)
FROM mfi_accounting.transaction_details WHERE account_number='{lan}' LIMIT 1;
"""
    )
    orig_off, off, gl_code, biz_date = (td_tmpl or "1|1|CG13334|NOW()").split("|", 3)
    psql_multi(
        f"""
INSERT INTO mfi_accounting.transaction_master (
  transaction_catalogue_id, reference_number, client_reference_number,
  operation_mode, client_code, channel_code, stan, currency, original_amount,
  status, business_date, transaction_value_date, transaction_date,
  created_by, approved_on, approved_by, updated_on, updated_by
) VALUES (
  {cat_id}, '{ref}', '{PROBE_TAG}_LP_{ref}',
  'SELF', 'NOVOPAY', 'NOVOPAY', '{stan}', '{currency}', 15.000000,
  'SUCCESS', '{biz_date}'::timestamp, '{biz_date}'::timestamp, NOW(),
  '{PROBE_TAG}', NOW(), '{PROBE_TAG}', NOW(), '{PROBE_TAG}'
);
INSERT INTO mfi_accounting.transaction_details (
  transaction_id, originating_office_id, office_id, account_number, gl_code,
  currency, net_amount, cr_dr_indicator, value_date, business_date, transaction_date,
  is_child_gl_code
) VALUES (
  currval(pg_get_serial_sequence('mfi_accounting.transaction_master','id')),
  {orig_off}, {off}, '{lan}', '{gl_code}',
  '{currency}', 15.000000, 'D', '{biz_date}'::timestamp, '{biz_date}'::timestamp, NOW(),
  false
);
INSERT INTO mfi_accounting.transaction_partition_details (
  transaction_id, reference_code, account_number, gl_code, office_id, currency,
  amount, source_amount, cr_dr_indicator, created_date, is_child_gl_code
) VALUES (
  currval(pg_get_serial_sequence('mfi_accounting.transaction_master','id')),
  'POS', '{gl_acct}', 'CG13578', {office}, '{currency}',
  15.000000, 15.000000, 'D', NOW(), true
);
"""
    )
    lp_tid = psql(
        f"SELECT id::text FROM mfi_accounting.transaction_master WHERE reference_number='{ref}';"
    )
    print(f"  synthetic LOAN_PREPAYMENT inserted ref={ref} id={lp_tid}")
    return lp_tid.strip(), ref


def proof_iii(lan: str) -> int:
    """Insert BPI_AMT AIR credit + balancer so per-txn D=C still holds — product AIR fails."""
    print(f"=== R0 proof_iii BPI-after-FB detector lan={lan} ===")
    aid = psql(
        f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{lan}';"
    )
    if not aid:
        print(f"FAIL: unknown lan {lan}")
        return 1

    fb = psql(
        f"""
SELECT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.la_account_number = '{lan}'
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ ('^' || la.account_id::text || '17[0-9]{{11}}([0-9]+)?$')
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    # Ensure FB detector engages: stamp client_ref on a BILLING if needed
    if not fb:
        bill = psql(
            f"""
SELECT tm.id::text||'|'||tm.client_reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_details td ON td.transaction_id = tm.id
WHERE td.account_number = '{lan}' AND tc.type = 'BILLING'
ORDER BY tm.id DESC LIMIT 1;
"""
        )
        if not bill:
            print("FAIL: proof_iii no BILLING txn to stamp FB CRN (cannot reproduce without fixture)")
            return 2
        tid, old_crn = bill.split("|", 1)
        stamp = str(int(time.time() * 1000))
        new_crn = f"{aid}17{stamp[-11:]}"
        psql_multi(
            f"""
UPDATE mfi_accounting.transaction_master
SET client_reference_number = '{new_crn}',
    updated_by = '{PROBE_TAG}'
WHERE id = {tid};
"""
        )
        print(f"  stamped FB CRN on BILLING id={tid} {old_crn} → {new_crn}")
        _fb_restore = (tid, old_crn)
    else:
        print(f"  existing force-bill ref={fb}")
        _fb_restore = None

    baseline = snapshot_invariants([lan])
    _lp_cleanup_ref: str | None = None
    lp_tid, lp_ref = _ensure_synthetic_loan_prepayment(lan, aid)
    _lp_cleanup_ref = lp_ref

    template = psql(
        f"""
SELECT office_id::text||'|'||currency||'|'||COALESCE(account_number,'')||'|'||COALESCE(is_child_gl_code::text,'f')
FROM mfi_accounting.transaction_partition_details
WHERE transaction_id = {lp_tid}
LIMIT 1;
"""
    )
    if not template:
        print("FAIL: proof_iii no partition template on txn")
        return 1
    office_id, currency, acct, child_gl = template.split("|", 3)
    if not acct:
        acct = "CG13578"
    print(f"  seeding BPI_AMT on txn_id={lp_tid} (per-txn stays balanced via balancer)")
    psql_multi(
        f"""
INSERT INTO mfi_accounting.transaction_partition_details (
  transaction_id, reference_code, account_number, gl_code, office_id, currency,
  amount, source_amount, cr_dr_indicator, created_date, is_child_gl_code
) VALUES
  ({lp_tid}, 'BPI_AMT', '{acct}', 'CG13578', {office_id}, '{currency}',
   15.000000, 15.000000, 'C', NOW(), true),
  ({lp_tid}, '{PROBE_TAG}_BAL', '{acct}', 'CG99999', {office_id}, '{currency}',
   15.000000, 15.000000, 'D', NOW(), true);
"""
    )
    bpi = bpi_air_credit_after_force_bill(lan)
    print(f"  seeded bpi_air_credit={bpi}")
    try:
        run_universal_invariants([lan], baseline=baseline, label="proof_iii")
        print("FAIL: proof_iii expected BPI-after-FB / AIR FAIL but PASSED")
        return 1
    except AssertionError as exc:
        msg = str(exc)
        if "BPI-after-FB" in msg or "FC settlement AIR" in msg or "392164" in msg:
            print(f"PASS: proof_iii caught 392164 class: {exc}")
            return 0
        print(f"FAIL: proof_iii failed for wrong reason: {exc}")
        return 1
    finally:
        psql_multi(
            f"""
DELETE FROM mfi_accounting.transaction_partition_details
WHERE transaction_id = {lp_tid}
  AND reference_code IN ('BPI_AMT', '{PROBE_TAG}_BAL');
"""
        )
        if _lp_cleanup_ref and _lp_cleanup_ref.startswith("R0LP"):
            psql_multi(
                f"""
DELETE FROM mfi_accounting.transaction_details WHERE transaction_id = {lp_tid};
DELETE FROM mfi_accounting.transaction_partition_details WHERE transaction_id = {lp_tid};
DELETE FROM mfi_accounting.transaction_master WHERE id = {lp_tid};
"""
            )
            print(f"  synthetic LOAN_PREPAYMENT removed ref={_lp_cleanup_ref}")
        if _fb_restore:
            tid, old_crn = _fb_restore
            psql_multi(
                f"""
UPDATE mfi_accounting.transaction_master
SET client_reference_number = '{old_crn}'
WHERE id = {tid};
"""
            )
        print("  probe partitions cleaned")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["ii", "iii"])
    ap.add_argument("--lan", default=os.environ.get("PROBE_LAN"))
    args = ap.parse_args()
    lan = _pick_lan(args.lan)
    if args.mode == "ii":
        return proof_ii(lan)
    return proof_iii(lan)


if __name__ == "__main__":
    sys.exit(main())
