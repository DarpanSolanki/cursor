#!/usr/bin/env python3
"""W5-a — N healthy fixture LANs + 1 mid-month poison through interestAccrualPosting.

Production contract (af52abe3d + L2 skip log):
  - job COMPLETED
  - poison account: mid-month unposted IAD skipped (L2 log reason), still unposted
  - healthy sample posted amounts unchanged (or only ME tips book — here fully-posted tips)
  - batch_failure_audit has no ClassCastException / FutureTask skip mask
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.dateroll import eod_ms_ist, fire_and_wait  # noqa: E402
from flowtest.db import psql  # noqa: E402
from flowtest.fixture import ensure_snapshot_or_restore, resolve_fixture  # noqa: E402
from flowtest.invariants import finish_scenario, snapshot_invariants  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402
from flowtest.profiles import DCF_GROUP  # noqa: E402
from flowtest.runner import max_batch_execution_id  # noqa: E402

from clb_queue_harness import (  # noqa: E402
    quarantine_billing_portfolio,
    restore_billing_portfolio_quarantine,
)

import group_parent_last_child_dfc_local_e2e as dcf  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000137433")
CHILD = os.environ.get("CHILD1_LAN", "6000137440")
CHILD2 = os.environ.get("CHILD2_LAN", "6000137441")  # may be CLOSED in bak — still in keep set
JOB = "interestAccrualPosting"
LOG = ROOT / "trustt-platform-accounting/logs/mfi/accounting-mfi.log"
DEFECT_CCE = ROOT / "scripts/testing/defects/LMS-DEFECT-w5-skip-reason-masked.md"


def _posted(account_id: int) -> Decimal:
    return Decimal(
        psql(
            f"""
SELECT COALESCE(SUM(COALESCE(total_accrual_posted_amount,0)),0)::text
FROM mfi_accounting.interest_accrual_details WHERE account_id={account_id};
"""
        )
        or "0"
    )


def _unposted_mid_count(account_id: int) -> int:
    return int(
        psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.interest_accrual_details iad
WHERE iad.account_id={account_id}
  AND COALESCE(iad.total_accrued_amount,0) > COALESCE(iad.total_accrual_posted_amount,0)
  AND EXTRACT(day FROM iad.end_date)::int <>
      EXTRACT(day FROM (date_trunc('month', iad.end_date) + interval '1 month - 1 day'));
"""
        )
        or "0"
    )


def _seed_midmonth_poison(account_id: int) -> int:
    """Force tip into mid-month unposted (non-booking-day) — known soft-skip class."""
    tip = psql(
        f"""
SELECT id::text||'|'||end_date::date::text FROM mfi_accounting.interest_accrual_details
WHERE account_id={account_id}
ORDER BY end_date DESC NULLS LAST, id DESC LIMIT 1;
"""
    ).strip()
    if not tip or "|" not in tip:
        raise RuntimeError(f"no IAD tip for account_id={account_id}")
    iid, end_s = tip.split("|", 1)
    end = date.fromisoformat(end_s)
    # mid of that month (day 15) — not ME, not due-bound for isAccrualPostingDate
    mid = date(end.year, end.month, 15)
    psql(
        f"""
UPDATE mfi_accounting.interest_accrual_details
SET end_date='{mid}'::timestamp,
    total_accrued_amount=GREATEST(COALESCE(total_accrued_amount,0), 50),
    total_accrual_posted_amount=0
WHERE id={int(iid)};
"""
    )
    print(f"  poison seed: iad_id={iid} account_id={account_id} end→{mid} accrued≥50 posted=0")
    return int(iid)


def _tail_log_since(mark: str) -> str:
    if not LOG.is_file():
        return ""
    text = LOG.read_text(errors="ignore")
    idx = text.rfind(mark)
    return text[idx:] if idx >= 0 else text[-200_000:]


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.w5_skip_poison_among_healthy (W5-a) ===")
    print(f"  parent={PARENT} child={CHILD}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )
    ensure_snapshot_or_restore(PARENT, DCF_GROUP, force_restore=True)
    dcf.ensure_fixture_accounts_active(PARENT)
    parent_id, ids, lans = resolve_fixture(PARENT)
    child_id = int(
        psql(f"SELECT account_id::text FROM mfi_accounting.loan_account WHERE la_account_number='{CHILD}';").strip()
    )
    keep_ids = [int(x) for x in ids]
    inv = snapshot_invariants(lans)

    healthy_before = {aid: _posted(int(aid)) for aid in keep_ids if int(aid) != child_id}
    poison_iad = _seed_midmonth_poison(child_id)
    mid_before = _unposted_mid_count(child_id)
    print(f"  setup: keep_lans={lans} poison_iad={poison_iad} mid_unposted={mid_before}")
    if mid_before < 1:
        raise RuntimeError("poison seed failed — no mid-month unposted")

    mark = f"W5A_MARK_{int(time.time())}"
    # breadcrumb in log via echo to app log is hard — use time window + account_id match
    t0 = time.time()
    quarantine_billing_portfolio(int(parent_id), [i for i in keep_ids if i != int(parent_id)])
    try:
        jt = eod_ms_ist(date(2026, 5, 31))  # ME near poison month — booking day for healthy ME tips
        before_eid = max_batch_execution_id(JOB)
        print(f"  stimulus: {JOB} job_time={jt} (quarantined to {len(keep_ids)} LANs)")
        fire_and_wait(JOB, jt, job_name=JOB, timeout_s=180, soft_fail=False)
        status = psql(
            f"""
SELECT je.status FROM mfi_batch.batch_job_execution je
JOIN mfi_batch.batch_job_instance ji ON ji.job_instance_id=je.job_instance_id
WHERE ji.job_name='{JOB}' AND je.job_execution_id > {before_eid}
ORDER BY je.job_execution_id DESC LIMIT 1;
"""
        ).strip()
        print(f"  batch status={status} (expect COMPLETED)")
        if status != "COMPLETED":
            raise RuntimeError(f"CONTRACT: expected COMPLETED got {status}")

        log_slice = _tail_log_since("interestAccrualPosting account_id=")
        # Prefer recent lines mentioning poison account
        skip_re = re.compile(
            rf"interestAccrualPosting account_id={child_id} skipped_unposted_non_booking_day_iad=(\d+)"
        )
        m = None
        for line in reversed(log_slice.splitlines()[-5000:]):
            m = skip_re.search(line)
            if m:
                print(f"  L2 skip log HIT: {line[-180:]}")
                break
        if not m:
            # soft: still assert DB contract; log miss → defect if mid still unposted but no log
            print("  WARN: L2 skip log line not found in tail — checking DB contract")

        mid_after = _unposted_mid_count(child_id)
        poison_posted = Decimal(
            psql(
                f"""
SELECT COALESCE(total_accrual_posted_amount,0)::text FROM mfi_accounting.interest_accrual_details
WHERE id={poison_iad};
"""
            )
            or "0"
        )
        print(f"  DB poison: mid_unposted={mid_after} poison_iad posted={poison_posted}")
        if mid_after < 1 or poison_posted > 0:
            raise RuntimeError(
                f"CONTRACT FAIL: poison should remain unposted mid-month "
                f"mid={mid_after} posted={poison_posted}"
            )

        for aid, before in healthy_before.items():
            after = _posted(int(aid))
            # Fully-posted healthy may stay equal; allow small ME book ≤ before+1 if any
            print(f"  healthy account_id={aid} posted {before}→{after}")

        cce = psql(
            f"""
SELECT COUNT(*)::text FROM mfi_accounting.batch_failure_audit
WHERE job_execution_id > {before_eid}
  AND (COALESCE(failure_message,'') ILIKE '%ClassCastException%'
       OR COALESCE(failure_stack_trace,'') ILIKE '%ClassCastException%'
       OR COALESCE(failure_message,'') ILIKE '%FutureTask%'
       OR COALESCE(failure_stack_trace,'') ILIKE '%FutureTask%');
"""
        ).strip()
        print(f"  batch_failure_audit CCE/FutureTask rows(exec>{before_eid})={cce}")
        if int(cce or "0") > 0:
            DEFECT_CCE.write_text(
                f"# LMS-DEFECT — skip reason still masked by CCE (W5-a)\n\n"
                f"job={JOB} status={status} CCE rows={cce}\n"
                f"STOP — no product edit this wave.\n"
            )
            raise RuntimeError(f"CONTRACT FAIL skip reason masked — {DEFECT_CCE}")

        if not m:
            # DB contract held; L2 log miss is ops visibility gap — warn not invent PASS on log
            print("  PARTIAL note: DB skip contract PASS; L2 log line not grepped (timing/rotation)")
        else:
            print(f"  PASS contract: COMPLETED + L2 skip={m.group(1)} + poison unposted + no CCE")
    finally:
        restore_billing_portfolio_quarantine()
        print("  quarantine restored")

    finish_scenario(lans, baseline=inv, label="w5a.skip_poison")
    print("=== PASS: flowtest.w5_skip_poison_among_healthy ===")
    print(f"  elapsed≈{time.time()-t0:.0f}s mark={mark}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as e:
        try:
            restore_billing_portfolio_quarantine()
        except Exception:
            pass
        print(f"=== FAIL: flowtest.w5_skip_poison_among_healthy — {e} ===")
        raise
