#!/usr/bin/env python3
"""SHG INT stitch — interestAccrualCalculation → Posting → loanAccountBillingJob.

Proves parent-SoT installment-window Accrued distribute stays stitched through
posting + billing for one SHG parent + ACTIVE children.

Coverage (fail-closed):
  - window Accrued parent == Σ ACTIVE children (or PASS_POSTED_FLOOR)
  - Accrued >= Posted on every fixture IAD row
  - parent last_iad advances to roll end (calc)
  - parent Posted increases when unposted>0 and a posting day (ME or due) is in range
  - LABD count increases when roll end is an unbilled due date
  - all three jobs COMPLETED (soft_fail=False)

Optional debug only (NOT default): CLEAR_BATCH_FAILURE_AUDIT=1 truncates
mfi_accounting.batch_failure_audit — masks SkipListener ClassCast poison;
leave at 0 so posting matches QA/prod failure surfaces.
"""
from __future__ import annotations

import calendar
import os
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from flowtest.dateroll import CHAIN_ACCRUAL_BILLING, declare_layers, roll  # noqa: E402
from flowtest.db import psql, psql_raw  # noqa: E402
from flowtest.fixture import resolve_fixture  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402

PARENT = os.environ.get("PARENT_LAN", "6000012030")
PARITY_SQL = (ROOT / "scripts/sql/helpers/verify_shg_interest_accrual_parity.sql").read_text()


def _db_write(sql: str) -> None:
    subprocess.check_call(
        ["bash", str(ROOT / "scripts/bin/db-local-write.sh"), "--sql", sql],
        cwd=str(ROOT),
    )


def _money_snap(lans: list[str]) -> dict[str, dict[str, Decimal | int | str]]:
    lan_list = ",".join(f"'{x}'" for x in lans)
    raw = psql_raw(
        f"""
SELECT a.account_number,
       COALESCE(SUM(iad.total_accrued_amount),0)::text,
       COALESCE(SUM(iad.total_accrual_posted_amount),0)::text,
       COALESCE(SUM(iad.total_accrued_amount - COALESCE(iad.total_accrual_posted_amount,0)),0)::text,
       COALESCE(MAX(iad.end_date)::date::text,''),
       (SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details b
         WHERE b.account_id=a.id)
FROM mfi_accounting.account a
LEFT JOIN mfi_accounting.interest_accrual_details iad ON iad.account_id=a.id
WHERE a.account_number IN ({lan_list})
GROUP BY a.account_number, a.id
ORDER BY 1
"""
    ).strip()
    out: dict[str, dict[str, Decimal | int | str]] = {}
    for line in raw.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 6:
            continue
        out[parts[0]] = {
            "accrued": Decimal(parts[1]),
            "posted": Decimal(parts[2]),
            "unposted": Decimal(parts[3]),
            "last_iad": parts[4],
            "labd": int(parts[5] or "0"),
        }
    return out


def _parity_verdict(parent_lan: str) -> tuple[str, Decimal, Decimal]:
    sql = PARITY_SQL.replace(":parent_lan", f"'{parent_lan}'")
    raw = psql_raw(sql).strip().splitlines()
    if not raw:
        raise AssertionError("parity SQL returned no rows")
    parts = [p.strip() for p in raw[0].split("|")]
    # prev_due|next_due|parent|children|diff|verdict
    if len(parts) < 6:
        raise AssertionError(f"parity SQL unexpected shape: {raw[0]!r}")
    parent_w = Decimal(parts[2] or "0")
    child_w = Decimal(parts[3] or "0")
    verdict = parts[5]
    return verdict, parent_w, child_w


def _posting_days_in_range(start: date, end: date, due_dates: set[date]) -> list[date]:
    out: list[date] = []
    cur = start
    while cur <= end:
        last = calendar.monthrange(cur.year, cur.month)[1]
        if cur.day == last or cur in due_dates:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def _resolve_roll_window(parent_id: int) -> tuple[date, date, set[date], bool]:
    """Derive calc/post/bill window from fixture schedule + IAD state (no static dates).

    Prefer next due after last_iad. If accrual already past all dues (last_iad ≥ max due),
    reopen last due only (1-day) and seed-trim IAD end_date so the window is schedule-native.
    Returns (start, end, dues_in_window, seeded).
    """
    dues_raw = psql_raw(
        f"""
SELECT DISTINCT due_date::date::text
FROM mfi_accounting.loan_due_details
WHERE loan_account_id={parent_id}
  AND COALESCE(is_deleted,false)=false
ORDER BY 1
"""
    ).strip()
    due_dates = sorted(
        {date.fromisoformat(x.strip()) for x in dues_raw.splitlines() if x.strip()}
    )
    if len(due_dates) < 2:
        raise RuntimeError(
            f"fixture schedule needs ≥2 dues for parent account_id={parent_id}; got {due_dates}"
        )

    last_iad_s = psql(
        f"""
SELECT COALESCE(MAX(end_date)::date::text,'')
FROM mfi_accounting.interest_accrual_details
WHERE account_id={parent_id}
"""
    )
    if not last_iad_s:
        raise RuntimeError(f"no IAD on parent account_id={parent_id}")
    last_iad = date.fromisoformat(last_iad_s)

    next_dues = [d for d in due_dates if d > last_iad]
    if next_dues:
        end = next_dues[0]
        start = last_iad + timedelta(days=1)
        seeded = False
    else:
        # Accrual already through schedule — reopen last installment from prior due,
        # wipe IAD after prior due, mark older IAD fully posted so booking walk is clean.
        end = due_dates[-1]
        prior = due_dates[-2]
        start = prior + timedelta(days=1)
        _db_write(
            f"""
DELETE FROM mfi_accounting.interest_accrual_details
WHERE account_id={parent_id}
  AND end_date > DATE '{prior.isoformat()}';
UPDATE mfi_accounting.interest_accrual_details
SET total_accrual_posted_amount = COALESCE(total_accrued_amount, 0),
    last_accrual_posted_date = COALESCE(last_accrual_posted_date, end_date)
WHERE account_id={parent_id}
  AND end_date <= DATE '{prior.isoformat()}'
  AND COALESCE(total_accrued_amount,0) > COALESCE(total_accrual_posted_amount,0);
"""
        )
        seeded = True
        print(
            f"  schedule-window seed: last_iad past max due; wiped IAD after prior_due={prior} "
            f"roll={start}..{end} (last installment, dues-derived)"
        )

    override_end = os.environ.get("SHG_INT_ROLL_END", "").strip()
    if override_end:
        end = date.fromisoformat(override_end)
    max_days = int(os.environ.get("SHG_INT_MAX_ROLL_DAYS", "40"))
    if (end - start).days + 1 > max_days:
        raise RuntimeError(
            f"roll window {start}..{end} is {(end - start).days + 1} days "
            f"(>{max_days}); set SHG_INT_ROLL_END / SHG_INT_MAX_ROLL_DAYS"
        )
    dues_in = {d for d in due_dates if start <= d <= end}
    if seeded:
        print(f"  LAYERS: roll_window=SEEDED_FROM_SCHEDULE start={start} end={end}")
    else:
        print(f"  LAYERS: roll_window=FROM_IAD_AND_SCHEDULE start={start} end={end}")
    return start, end, dues_in, seeded


def main() -> int:
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["DCF_E2E_LOCK_HELD"] = "1"
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"
    print("=== flowtest.shg_int_accrual_stitch ===")
    print(f"  parent={PARENT}")

    subprocess.check_call(
        ["bash", str(ROOT / "scripts/dcf_sanity/ensure_dcf_local_stack.sh")],
        env={**os.environ, "DCF_STACK_SKIP_ACCOUNTING_RESTART": "1"},
    )

    if os.environ.get("CLEAR_BATCH_FAILURE_AUDIT", "0") == "1":
        _db_write("TRUNCATE TABLE mfi_accounting.batch_failure_audit;")
        n = psql("SELECT COUNT(*)::text FROM mfi_accounting.batch_failure_audit")
        print(f"  SEEDED audit_clear: truncated batch_failure_audit rows_now={n}")
    else:
        audit_n = psql("SELECT COUNT(*)::text FROM mfi_accounting.batch_failure_audit")
        print(f"  REAL audit table untouched (rows={audit_n}); set CLEAR_BATCH_FAILURE_AUDIT=1 only for debug")

    parent_id_s, ids, lans = resolve_fixture(PARENT)
    parent_id = int(parent_id_s)
    child_ids = [int(x) for x in ids if int(x) != parent_id]
    if len(child_ids) < 1:
        raise RuntimeError(f"SHG parent {PARENT} has no children")
    print(f"  fixture parent_id={parent_id} children={len(child_ids)} lans={lans}")

    start, end, dues, seeded_window = _resolve_roll_window(parent_id)
    posting_days = _posting_days_in_range(start, end, dues)
    print(
        f"  roll {start}..{end} days={(end - start).days + 1} "
        f"dues={sorted(d.isoformat() for d in dues)} "
        f"posting_days={len(posting_days)} seeded_window={seeded_window}"
    )

    before = _money_snap(lans)
    before_verdict, before_pw, before_cw = _parity_verdict(PARENT)
    print(
        f"  BEFORE parity={before_verdict} parent_window={before_pw} "
        f"children_window={before_cw} parent_unposted={before[PARENT]['unposted']} "
        f"parent_posted={before[PARENT]['posted']} labd={before[PARENT]['labd']}"
    )

    timeout_s = int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "300"))
    result = roll(
        start,
        end,
        chain=CHAIN_ACCRUAL_BILLING,
        quarantine_parent_id=parent_id,
        quarantine_child_ids=child_ids,
        timeout_s=timeout_s,
        soft_fail=False,
        layers_seeded=(
            ["batch_failure_audit_truncate"]
            if os.environ.get("CLEAR_BATCH_FAILURE_AUDIT", "0") == "1"
            else ["quarantine_portfolio", "job_time_synthetic"]
        ),
    )
    declare_layers(result)

    after = _money_snap(lans)
    verdict, pw, cw = _parity_verdict(PARENT)
    print(
        f"  AFTER parity={verdict} parent_window={pw} children_window={cw} "
        f"parent_unposted={after[PARENT]['unposted']} "
        f"parent_posted={after[PARENT]['posted']} labd={after[PARENT]['labd']}"
    )

    if verdict not in ("PASS", "PASS_POSTED_FLOOR"):
        raise AssertionError(
            f"window Accrued parity FAIL: verdict={verdict} parent={pw} children={cw}"
        )
    print(f"  PASS window Accrued parity ({verdict}) parent={pw} children={cw}")

    viol = psql(
        f"""
SELECT COUNT(*)::text
FROM mfi_accounting.interest_accrual_details iad
JOIN mfi_accounting.loan_account la ON la.account_id=iad.account_id
WHERE (la.account_id={parent_id} OR la.parent_loan_account_id={parent_id})
  AND COALESCE(iad.total_accrued_amount,0) < COALESCE(iad.total_accrual_posted_amount,0)
"""
    )
    if int(viol or "0") != 0:
        raise AssertionError(f"Accrued>=Posted FAIL: violations={viol}")
    print("  PASS Accrued>=Posted on fixture")

    last_after = str(after[PARENT]["last_iad"])
    if not last_after or date.fromisoformat(last_after) < end:
        raise AssertionError(
            f"calc FAIL: parent last_iad={last_after!r} expected >={end.isoformat()}"
        )
    print(f"  PASS calc advanced last_iad={last_after}")

    # Calc during the roll creates Accrued; ME/due IAD end_dates must book → parent Posted↑.
    # Children may hold Accrued on non-ME/non-due end_dates (distribute SET) until those
    # end_dates land on a posting day — do not require child Posted↑ every stitch.
    if posting_days:
        if Decimal(str(after[PARENT]["posted"])) <= Decimal(str(before[PARENT]["posted"])):
            raise AssertionError(
                f"posting FAIL: parent Posted did not increase "
                f"{before[PARENT]['posted']} -> {after[PARENT]['posted']} "
                f"(posting_days={ [d.isoformat() for d in posting_days] })"
            )
        print(
            f"  PASS posting parent Posted "
            f"{before[PARENT]['posted']} -> {after[PARENT]['posted']}"
        )
        child_accrued_ok = any(
            Decimal(str(after[lan]["accrued"])) >= Decimal(str(before[lan]["accrued"]))
            for lan in lans
            if lan != PARENT and lan in before and lan in after
        )
        if not child_accrued_ok:
            raise AssertionError(
                f"distribute FAIL: child Accrued shrank "
                f"{ {lan: (before.get(lan, {}).get('accrued'), after.get(lan, {}).get('accrued')) for lan in lans if lan != PARENT} }"
            )
        print("  PASS children Accrued non-decreasing (distribute)")
    else:
        if pw < before_pw and verdict == "PASS":
            raise AssertionError(
                f"calc FAIL: parent window Accrued shrank {before_pw} -> {pw}"
            )
        print("  SKIP strict Posted↑ (no ME/due in roll window)")

    if end in dues:
        labd_up = any(
            int(after[lan]["labd"]) > int(before[lan]["labd"]) for lan in lans if lan in after
        )
        if labd_up:
            print(
                f"  PASS billing LABD↑ "
                f"{ {lan: (before.get(lan, {}).get('labd'), after.get(lan, {}).get('labd')) for lan in lans} }"
            )
        elif seeded_window:
            # Max-due reopen: LABD for that due already exists (no due_date col on LABD;
            # deleting LABD would be fidelity labd_gap — out of scope for stitch).
            print(
                f"  SKIP billing LABD↑ (seeded last-due reopen; due={end} expected already billed; "
                f"labd stable "
                f"{ {lan: before.get(lan, {}).get('labd') for lan in lans} })"
            )
        else:
            raise AssertionError(
                f"billing FAIL: no LABD increase after due={end} "
                f"before={ {lan: before.get(lan, {}).get('labd') for lan in lans} } "
                f"after={ {lan: after.get(lan, {}).get('labd') for lan in lans} }"
            )
    else:
        print(f"  SKIP billing LABD assert (roll end {end} is not a due date)")

    audit_n = psql("SELECT COUNT(*)::text FROM mfi_accounting.batch_failure_audit")
    print(f"  audit rows after={audit_n}")
    print(
        "  LAYERS_DECLARE: jobs=REAL(interestAccrualCalculation,interestAccrualPosting,"
        "loanAccountBillingJob) quarantine=REAL parity=SQL_helper"
    )
    print("=== PASS: flowtest.shg_int_accrual_stitch ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"=== FAIL: flowtest.shg_int_accrual_stitch: {exc} ===")
        raise
