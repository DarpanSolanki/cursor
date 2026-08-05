#!/usr/bin/env python3
"""Fresh-disbursed loan → interestAccrualCalculation → Posting → loanAccountBillingJob.

Why this exists (gap the aged-fixture suites could not see)
-----------------------------------------------------------
`flowtest.shg_int_accrual_stitch` and `flowtest.accrual_billing` both reuse loans
that already carry IAD/LABD history and seed their roll window from existing IAD
rows. Neither ever walks a loan from **zero accrual state** (0 IAD, 0 LABD) across
its first month-end and its first due date. Two defects only a fresh loan shows:

  1. product 2 (JLG) had no `product__transaction_catalogue` row for
     BILLING/NORMAL_BILLING → `loanAccountBillingJob` FAILS with 134207 on the
     first due date. Calc and posting pass for 30 days first, so a suite that
     only checks "accrual moved" reports green.
  2. the due-date true-up (`getAccruedInterestOnDueDate`) makes the final segment
     = scheduled INT − already-accrued, NOT day-count × rate. A pure day-count
     assert would flag a correct run, and a sum-only assert would miss a wrong
     split.

Fail-closed asserts (all value-level, no presence-only)
------------------------------------------------------
  A. preflight: BILLING catalogue + every placeholder the accounting rules
     reference resolves to an internal account definition (catches 134207 up
     front instead of after a 30-day roll)
  B. baseline is genuinely fresh: 0 IAD, 0 LABD on parent and children
  C. IAD segments contiguous — no gap, no overlap; first start == disbursement
     date; last end == roll end
  D. a segment boundary lands on every posting day (month-end + due date) in the
     window
  E. per-installment: SUM(IAD.total_accrued_amount) == scheduled INT due_amount
  F. non-due segments follow base x rate/100 / DIY x days (+/- rounding)
  G. posted == accrued and last_accrual_posted_date == end_date on posting days
  H. every IAD row carries loan_installment_details_id, and it is the installment
     whose window contains the segment
  I. LABD for the billed installment: interest == scheduled INT, principal ==
     scheduled PRIN, billing_amount == installment_amount == principal + interest
  J. BILLING transaction GL legs balance (SUM debit == SUM credit) and the
     interest leg equals the billed interest
  K. SHG only: SUM(children accrued) == parent accrued over the window, and each
     child IAD row carries its OWN installment id (never the parent's) — the
     `ad399c5f2` / `60e2c0ab9` contract

Usage
-----
  LAN=6004162725 python3 scripts/testing/flowtest/scenarios/fresh_loan_int_accrual_e2e.py
  LAN=6004162825 ...            # SHG parent — children resolved automatically

Re-runs reseed the fixture (parent AND children) back to zero accrual before the
roll, so the case stays a true first-cycle walk instead of drifting into an aged
fixture — which is exactly how the existing suites lost this coverage.

Env: LAN (required), FRESH_INT_MAX_ROLL_DAYS (default 40),
     FLOWTEST_BATCH_TIMEOUT (default 300), FRESH_INT_ALLOW_DIRTY=1 to keep
     existing accrual state and skip B (inspection only — not a pass mode).
"""
from __future__ import annotations

import calendar
import os
import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts/testing"))
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from clb_queue_harness import (  # noqa: E402
    quarantine_billing_portfolio,
    restore_billing_portfolio_quarantine,
)
from flowtest.dateroll import (  # noqa: E402
    CHAIN_ACCRUAL_BILLING,
    declare_layers,
    eod_ms_ist,
    fire_and_wait,
    roll,
)
from flowtest.db import psql, psql_multi, psql_raw  # noqa: E402
from flowtest.lock import acquire_flowtest_lock, mark_lock_held  # noqa: E402

LAN = os.environ.get("LAN", "").strip()
MAX_ROLL_DAYS = int(os.environ.get("FRESH_INT_MAX_ROLL_DAYS", "40"))
# Rounding slack: interest_rounding_factor 0 rounds each segment to the rupee.
ROUND_SLACK = Decimal(os.environ.get("FRESH_INT_ROUND_SLACK", "1"))

FAILURES: list[str] = []


def check(ok: bool, label: str, detail: str = "") -> None:
    if ok:
        print(f"  PASS {label}" + (f" — {detail}" if detail else ""))
    else:
        print(f"  FAIL {label} — {detail}")
        FAILURES.append(f"{label}: {detail}")


def rows(sql: str) -> list[list[str]]:
    raw = psql_raw(sql).strip()
    if not raw:
        return []
    return [[c.strip() for c in line.split("|")] for line in raw.splitlines() if line.strip()]


def d(x: str) -> Decimal:
    return Decimal(x or "0")


# --------------------------------------------------------------------------- #
# loan / schedule resolution
# --------------------------------------------------------------------------- #
def resolve_loan(lan: str) -> dict:
    r = rows(
        f"""
SELECT la.account_id, la.la_account_number, la.loan_status, la.parent_loan_account_id,
       la.expected_disbursement_date::date, lp.product_id, lp.id,
       ps.interest_calculation_days_in_year, ps.interest_calculation_days_in_month,
       la.approved_amount, lp.interest_rounding_factor
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
JOIN mfi_accounting.product_scheme ps ON ps.id = la.la_product_scheme_id
WHERE la.la_account_number = '{lan}'
"""
    )
    if not r:
        raise SystemExit(f"LAN not found: {lan}")
    x = r[0]
    if x[3]:
        raise SystemExit(
            f"{lan} is an SHG child (parent_loan_account_id={x[3]}); "
            "run the scenario on the parent — children are excluded at the calc reader"
        )
    if x[2] != "ACTIVE":
        raise SystemExit(f"{lan} loan_status={x[2]}; accrual reader selects ACTIVE only")
    kids = rows(
        f"SELECT account_id, la_account_number FROM mfi_accounting.loan_account "
        f"WHERE parent_loan_account_id={x[0]} AND COALESCE(is_deleted,false)=false ORDER BY account_id"
    )
    return {
        "account_id": int(x[0]),
        "lan": x[1],
        "disb_date": date.fromisoformat(x[4]),
        "product_id": int(x[5]),
        "days_in_year": x[7],
        "days_in_month": x[8],
        "base_amount": d(x[9]),
        "child_ids": [int(k[0]) for k in kids],
        "child_lans": [k[1] for k in kids],
    }


def schedule(account_id: int) -> list[dict]:
    """Installments with their scheduled INT / PRIN dues, ordered by date."""
    out = []
    for r in rows(
        f"""
SELECT li.id, li.installment_date::date, li.installment_amount,
       COALESCE((SELECT SUM(due_amount) FROM mfi_accounting.loan_due_details
                 WHERE loan_installment_details_id = li.id AND component_type = 'INT'
                   AND COALESCE(is_deleted,false)=false),0),
       COALESCE((SELECT SUM(due_amount) FROM mfi_accounting.loan_due_details
                 WHERE loan_installment_details_id = li.id AND component_type = 'PRIN'
                   AND COALESCE(is_deleted,false)=false),0)
FROM mfi_accounting.loan_installment_details li
WHERE li.loan_account_id = {account_id} AND COALESCE(li.is_deleted,false)=false
ORDER BY li.installment_date, li.id
"""
    ):
        out.append(
            {
                "lid": int(r[0]),
                "due_date": date.fromisoformat(r[1]),
                "installment_amount": d(r[2]),
                "int_due": d(r[3]),
                "prin_due": d(r[4]),
            }
        )
    if not out:
        raise SystemExit(f"no schedule for account_id={account_id}")
    return out


def iad_rows(account_id: int) -> list[dict]:
    out = []
    for r in rows(
        f"""
SELECT start_date::date, end_date::date, base_amount, interest_rate,
       total_accrued_amount, COALESCE(carry_over_amount,0),
       COALESCE(total_accrual_posted_amount,0),
       COALESCE(last_accrual_posted_date::date::text,''),
       COALESCE(loan_installment_details_id::text,'')
FROM mfi_accounting.interest_accrual_details
WHERE account_id = {account_id} ORDER BY start_date, end_date
"""
    ):
        out.append(
            {
                "start": date.fromisoformat(r[0]),
                "end": date.fromisoformat(r[1]),
                "base": d(r[2]),
                "rate": d(r[3]),
                "accrued": d(r[4]),
                "carry": d(r[5]),
                "posted": d(r[6]),
                "lapd": date.fromisoformat(r[7]) if r[7] else None,
                "lid": int(r[8]) if r[8] else None,
            }
        )
    return out


# --------------------------------------------------------------------------- #
# A — 134207 preflight
# --------------------------------------------------------------------------- #
def preflight_billing_catalogue(product_id: int) -> None:
    print(f"→ A. BILLING catalogue preflight (product_id={product_id})")
    ptc = psql(
        f"""
SELECT ptc.id::text FROM mfi_accounting.product__transaction_catalogue ptc
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ptc.transaction_catalogue_id
WHERE ptc.product_id = {product_id} AND tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND COALESCE(ptc.is_deleted,false)=false
"""
    )
    check(
        bool(ptc),
        "product↔BILLING/NORMAL_BILLING catalogue link exists",
        f"product_id={product_id}"
        + (
            ""
            if ptc
            else " — loanAccountBillingJob will fail 134207; apply "
            "scripts/sql/setup/local_setup_jlg_billing_catalogue_placeholder_iad.sql"
        ),
    )
    if not ptc:
        return
    missing = rows(
        f"""
WITH needed AS (
  SELECT DISTINCT p AS placeholder_code
  FROM mfi_accounting.transaction_accounting_rule r,
       LATERAL (VALUES (r.debit_account_placeholder),
                       (r.credit_account_placeholder),
                       (r.fallback_credit_placeholder)) AS v(p)
  WHERE r.transaction_catalogue_id = (
          SELECT id FROM mfi_accounting.transaction_catalogue
          WHERE type='BILLING' AND sub_type='NORMAL_BILLING' AND COALESCE(is_deleted,false)=false LIMIT 1)
    AND COALESCE(r.is_deleted,false)=false AND p IS NOT NULL AND p <> ''
)
SELECT n.placeholder_code FROM needed n
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
  WHERE x.product_transaction_catalogue_id = {ptc}
    AND x.placeholder_code = n.placeholder_code AND COALESCE(x.is_deleted,false)=false)
ORDER BY 1
"""
    )
    check(
        not missing,
        "every BILLING placeholder resolves to an internal account definition",
        "missing=" + ",".join(m[0] for m in missing) if missing else "all mapped",
    )


# --------------------------------------------------------------------------- #
# window + posting days
# --------------------------------------------------------------------------- #
def reseed(account_ids: list[int]) -> None:
    """Drop accrual + billing artefacts for the whole fixture (local DB only).

    Deletes the BILLING transaction and its GL legs too — leaving them behind
    would let assert J pass against a stale transaction from a previous run.
    """
    ids = ",".join(str(i) for i in account_ids)
    txn_ids = " ".join(
        r[0]
        for r in rows(
            f"""
SELECT tm.id::text FROM mfi_accounting.transaction_master tm
WHERE tm.reference_number IN (
  SELECT transaction_reference_number FROM mfi_accounting.loan_account_billing_details
  WHERE account_id IN ({ids}) AND transaction_reference_number IS NOT NULL)
"""
        )
    ).replace(" ", ",")
    # One statement per call: Yugabyte evaluates the FK check against the
    # transaction snapshot, so batching the child + parent deletes together
    # fails on fk_transaction_partition_details_transaction_master1.
    stmts = []
    if txn_ids:
        # Every FK child of transaction_master (pg_constraint confrelid), not just
        # the partition details — transaction_details and transaction_metadata
        # reference it too and each one blocks the parent delete in turn.
        for child in (
            "transaction_partition_details",
            "transaction_details",
            "transaction_metadata",
        ):
            stmts.append(
                f"DELETE FROM mfi_accounting.{child} WHERE transaction_id IN ({txn_ids});"
            )
        stmts.append(f"DELETE FROM mfi_accounting.transaction_master WHERE id IN ({txn_ids});")
    stmts.append(f"DELETE FROM mfi_accounting.loan_account_billing_details WHERE account_id IN ({ids});")
    stmts.append(f"DELETE FROM mfi_accounting.interest_accrual_details WHERE account_id IN ({ids});")
    for s in stmts:
        psql_multi(s)


def posting_days(start: date, end: date, dues: set[date]) -> list[date]:
    out, cur = [], start
    while cur <= end:
        if cur.day == calendar.monthrange(cur.year, cur.month)[1] or cur in dues:
            out.append(cur)
        cur += timedelta(days=1)
    return out


def installment_for(seg_end: date, sched: list[dict], disb: date) -> int | None:
    """Installment whose (previous due, due] window contains seg_end."""
    prev = disb
    for ins in sched:
        if prev < seg_end <= ins["due_date"]:
            return ins["lid"]
        prev = ins["due_date"]
    return None


def main() -> int:  # noqa: C901 — one linear proof, kept readable by sections
    if not LAN:
        raise SystemExit("set LAN=<parent or standalone LAN>")
    acquire_flowtest_lock()
    mark_lock_held()
    os.environ["FLOWTEST_E2E_LOCK_HELD"] = "1"

    print("=== flowtest.fresh_loan_int_accrual_e2e ===")
    loan = resolve_loan(LAN)
    is_shg = bool(loan["child_ids"])
    print(
        f"  lan={loan['lan']} account_id={loan['account_id']} product_id={loan['product_id']} "
        f"children={len(loan['child_ids'])} disb={loan['disb_date']} "
        f"basis={loan['days_in_month']}/{loan['days_in_year']}"
    )

    preflight_billing_catalogue(loan["product_id"])

    sched = schedule(loan["account_id"])
    first_due = sched[0]["due_date"]
    start = loan["disb_date"] + timedelta(days=1)
    end = first_due
    span = (end - start).days + 1
    if span > MAX_ROLL_DAYS:
        raise SystemExit(
            f"roll window {start}..{end} is {span} days (>{MAX_ROLL_DAYS}); "
            "raise FRESH_INT_MAX_ROLL_DAYS if intended"
        )
    dues = {s["due_date"] for s in sched if start <= s["due_date"] <= end}
    pdays = posting_days(start, end, dues)
    print(
        f"  roll {start}..{end} days={span} first_due={first_due} "
        f"posting_days={[p.isoformat() for p in pdays]}"
    )
    if not pdays:
        raise SystemExit("window contains no month-end and no due date — nothing to post")

    # B — fresh baseline
    print("→ B. fresh baseline")
    all_ids = [loan["account_id"], *loan["child_ids"]]
    ids_csv = ",".join(str(i) for i in all_ids)
    n_iad = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.interest_accrual_details "
            f"WHERE account_id IN ({ids_csv})"
        )
        or "0"
    )
    n_labd = int(
        psql(
            f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details "
            f"WHERE account_id IN ({ids_csv})"
        )
        or "0"
    )
    if os.environ.get("FRESH_INT_ALLOW_DIRTY") == "1":
        print(f"  SKIP fresh baseline (FRESH_INT_ALLOW_DIRTY=1) iad={n_iad} labd={n_labd}")
    elif n_iad or n_labd:
        # Re-runs accumulate state. Wipe the whole fixture — parent AND children —
        # back to zero accrual so the roll is a true first-cycle walk. Wiping only
        # one side is how a polluted fixture produces a green run.
        print(f"  RESEED to zero-accrual baseline (was iad={n_iad} labd={n_labd})")
        reseed(all_ids)
        n_iad = int(
            psql(
                f"SELECT COUNT(*)::text FROM mfi_accounting.interest_accrual_details "
                f"WHERE account_id IN ({ids_csv})"
            )
            or "0"
        )
        n_labd = int(
            psql(
                f"SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details "
                f"WHERE account_id IN ({ids_csv})"
            )
            or "0"
        )
        check(
            n_iad == 0 and n_labd == 0,
            "loan reseeded to zero accrual/billing history",
            f"iad={n_iad} labd={n_labd}",
        )
    else:
        check(True, "loan starts with zero accrual/billing history", "iad=0 labd=0")

    # ---- run the real jobs -------------------------------------------------
    # Days cannot be parallelised (day N+1 accrual reads day N's IAD), but they
    # need not all be fired: the calc job walks the intervening days internally
    # (InterestAccrualCalculationBatchService L203-212 loops until
    # totalDaysCountForAccrualCalculation). Firing only the posting days drops a
    # 30-day window from 90 executions to 6 — measured 72% of wall-clock was
    # psql-poll overhead per execution, not job runtime (~1.0s/job).
    # Cadence is part of the contract, but full daily firing is not required.
    # Measured on SHG parent 6004162825 (verified-current bytecode incl. ad399c5f2):
    #   posting_days   2 fires   23s  → K2 PASSES (defect hidden — under-fires)
    #   hop (+1/gap)   4 fires   32s  → K2 FAILS 307/306, 701/702  ← same as daily
    #   daily         34 fires  ~6min → K2 FAILS 307/306, 701/702
    # The per-segment break needs REPEATED re-distribution of the open segment, not
    # every calendar day: one intermediate calc per gap is sufficient and the other
    # 30 days add nothing. `hop` is therefore the default for group loans — same
    # fidelity, ~11x less wall. Standalone loans have no distribute step and are
    # byte-identical under posting_days (JLG 6004162725: 354/250, LABD
    # 604/1820/2424, GL D=C=2424). Use FRESH_INT_ROLL_MODE=daily for a full EOD walk.
    default_mode = "hop" if is_shg else "posting_days"
    mode = os.environ.get("FRESH_INT_ROLL_MODE", default_mode)
    if mode == "posting_days" and is_shg:
        print(
            "  WARNING roll mode=posting_days on a group loan — only 1 distribute per "
            "segment, so per-segment parity (K2) is NOT exercised; use hop or daily"
        )
    timeout_s = int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "300"))
    if mode == "daily":
        result = roll(
            start,
            end,
            chain=CHAIN_ACCRUAL_BILLING,
            quarantine_parent_id=loan["account_id"],
            quarantine_child_ids=loan["child_ids"],
            timeout_s=timeout_s,
            soft_fail=False,
            layers_seeded=["quarantine_portfolio", "job_time_synthetic"],
        )
        declare_layers(result)
    else:
        fire_days = list(pdays)
        if mode == "hop":
            # Posting days alone under-fire group loans: the SHG per-segment break
            # accrues from REPEATED re-distribution of the open segment, so it needs
            # >1 calc between boundaries — not all 34 days. Adding N intermediate
            # days per gap keeps the defect reachable at a fraction of the wall.
            extra = int(os.environ.get("FRESH_INT_HOP_INTERMEDIATE", "1"))
            prev = start - timedelta(days=1)
            augmented: list[date] = []
            for p in pdays:
                gap = (p - prev).days - 1
                if gap > 0 and extra > 0:
                    step = max(1, (gap + 1) // (extra + 1))
                    d0 = prev + timedelta(days=step)
                    while d0 < p and len(augmented) < 400:
                        augmented.append(d0)
                        d0 += timedelta(days=step)
                augmented.append(p)
                prev = p
            fire_days = sorted(set(augmented))
        print(
            f"  roll mode={mode} — firing {len(fire_days)} day(s) instead of {span} "
            f"(posting days: {[p.isoformat() for p in pdays]})"
        )
        quarantine_billing_portfolio(loan["account_id"], loan["child_ids"])
        try:
            for day in fire_days:
                jt = eod_ms_ist(day)
                print(f"  dateroll day={day.isoformat()} job_time={jt}")
                for api, jn in CHAIN_ACCRUAL_BILLING:
                    fire_and_wait(api, jt, job_name=jn, timeout_s=timeout_s, soft_fail=False)
        finally:
            restore_billing_portfolio_quarantine()
        print(
            "  LAYERS real=interestAccrualCalculation,interestAccrualPosting,"
            "loanAccountBillingJob seeded=quarantine_portfolio,job_time_synthetic,"
            "posting_days_only"
        )

    segs = iad_rows(loan["account_id"])
    if not segs:
        raise SystemExit("calc produced no IAD rows — accrual did not run on the fixture")
    for s in segs:
        print(
            f"    IAD {s['start']}..{s['end']} base={s['base']} rate={s['rate']} "
            f"accrued={s['accrued']} posted={s['posted']} lapd={s['lapd']} lid={s['lid']}"
        )

    # C — contiguity
    print("→ C. segment contiguity")
    check(segs[0]["start"] == loan["disb_date"], "first segment starts at disbursement date",
          f"{segs[0]['start']} vs {loan['disb_date']}")
    gaps = [
        f"{segs[i]['end']}→{segs[i + 1]['start']}"
        for i in range(len(segs) - 1)
        if segs[i]["end"] != segs[i + 1]["start"]
    ]
    check(not gaps, "segments contiguous (no gap, no overlap)", ",".join(gaps) or f"{len(segs)} segments")
    check(segs[-1]["end"] == end, "last segment ends at roll end", f"{segs[-1]['end']} vs {end}")

    # D — boundary on every posting day
    print("→ D. posting-day boundaries")
    bounds = {s["end"] for s in segs}
    missed = [p.isoformat() for p in pdays if p not in bounds]
    check(not missed, "a segment boundary lands on every month-end and due date",
          "missing=" + ",".join(missed) if missed else ",".join(p.isoformat() for p in pdays))

    # E — per-installment accrual == scheduled interest
    print("→ E. accrual reconciles to scheduled interest")
    for ins in sched:
        if not (start <= ins["due_date"] <= end):
            continue
        got = sum((s["accrued"] for s in segs if s["lid"] == ins["lid"]), Decimal(0))
        check(
            got == ins["int_due"],
            f"installment lid={ins['lid']} due={ins['due_date']} accrued == scheduled INT",
            f"accrued={got} scheduled={ins['int_due']}",
        )

    # F — non-due segments follow the day-count formula
    print("→ F. non-due segment day-count formula")
    diy = Decimal("360" if "360" in (loan["days_in_year"] or "") else "365")
    due_dates = {s["due_date"] for s in sched}
    for s in segs:
        if s["end"] in due_dates:
            continue  # due-date segment is trued-up to scheduled INT (E covers it)
        days = Decimal((s["end"] - s["start"]).days)
        expect = s["base"] * s["rate"] / Decimal(100) / diy * days
        check(
            abs(s["accrued"] - expect) <= ROUND_SLACK,
            f"segment {s['start']}..{s['end']} accrued == base×rate/{diy}×{days}",
            f"accrued={s['accrued']} expect≈{expect.quantize(Decimal('0.01'))}",
        )

    # G — posting
    print("→ G. posting on month-end / due date")
    for s in segs:
        if s["end"] not in bounds or s["end"] not in set(pdays):
            continue
        check(
            s["posted"] == s["accrued"],
            f"segment ending {s['end']} fully posted",
            f"posted={s['posted']} accrued={s['accrued']}",
        )
        check(
            s["lapd"] == s["end"],
            f"segment ending {s['end']} last_accrual_posted_date == end_date",
            f"lapd={s['lapd']}",
        )
    over = [f"{s['start']}..{s['end']}" for s in segs if s["posted"] > s["accrued"]]
    check(not over, "posted never exceeds accrued", ",".join(over) or "ok")

    # H — installment linkage
    print("→ H. installment linkage")
    bad = [
        f"{s['start']}..{s['end']} lid={s['lid']} expected={installment_for(s['end'], sched, loan['disb_date'])}"
        for s in segs
        if s["lid"] is None or s["lid"] != installment_for(s["end"], sched, loan["disb_date"])
    ]
    check(not bad, "every IAD row carries the installment covering its window", "; ".join(bad) or "ok")

    # I / J — billing + GL
    print("→ I. billing row values")
    billed = [ins for ins in sched if start <= ins["due_date"] <= end]
    for ins in billed:
        lr = rows(
            f"""
SELECT billing_amount, principal_amount, interest_amount, transaction_reference_number,
       transaction_value_date::date
FROM mfi_accounting.loan_account_billing_details
WHERE account_id = {loan['account_id']} AND loan_installment_details_id = {ins['lid']}
  AND COALESCE(reversed,false)=false
"""
        )
        check(len(lr) == 1, f"exactly one LABD for lid={ins['lid']}", f"rows={len(lr)}")
        if len(lr) != 1:
            continue
        b, p, i, txnref, vdate = d(lr[0][0]), d(lr[0][1]), d(lr[0][2]), lr[0][3], lr[0][4]
        check(i == ins["int_due"], f"LABD interest == scheduled INT (lid={ins['lid']})",
              f"{i} vs {ins['int_due']}")
        check(p == ins["prin_due"], f"LABD principal == scheduled PRIN (lid={ins['lid']})",
              f"{p} vs {ins['prin_due']}")
        check(b == ins["installment_amount"], f"LABD billing_amount == installment_amount (lid={ins['lid']})",
              f"{b} vs {ins['installment_amount']}")
        check(b == p + i, f"LABD billing_amount == principal + interest (lid={ins['lid']})",
              f"{b} vs {p}+{i}")
        check(vdate == ins["due_date"].isoformat(), f"LABD value date == due date (lid={ins['lid']})",
              f"{vdate} vs {ins['due_date']}")

        print("→ J. billing GL legs")
        legs = rows(
            f"""
SELECT tpd.reference_code, tpd.cr_dr_indicator, tpd.amount, tpd.gl_code
FROM mfi_accounting.transaction_partition_details tpd
JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_id
WHERE tm.reference_number = '{txnref}' ORDER BY tpd.id
"""
        )
        dr = sum((d(l[2]) for l in legs if l[1] == "D"), Decimal(0))
        cr = sum((d(l[2]) for l in legs if l[1] == "C"), Decimal(0))
        check(bool(legs) and dr == cr, f"BILLING GL balanced (lid={ins['lid']})",
              f"D={dr} C={cr} legs={len(legs)}")
        gl_int = sum((d(l[2]) for l in legs if l[0] == "interest_amount" and l[1] == "D"), Decimal(0))
        gl_prin = sum((d(l[2]) for l in legs if l[0] == "principal_amount" and l[1] == "D"), Decimal(0))
        check(gl_int == i, f"GL interest leg == billed interest (lid={ins['lid']})", f"{gl_int} vs {i}")
        check(gl_prin == p, f"GL principal leg == billed principal (lid={ins['lid']})", f"{gl_prin} vs {p}")

    # K — SHG distribute contract
    if is_shg:
        print("→ K. SHG parent→child distribute")
        parent_total = sum((s["accrued"] for s in segs), Decimal(0))
        child_total = Decimal(0)
        for cid in loan["child_ids"]:
            crows = iad_rows(cid)
            csum = sum((s["accrued"] for s in crows), Decimal(0))
            child_total += csum
            check(bool(crows), f"child {cid} received distributed IAD rows", f"rows={len(crows)}")
            csched = schedule(cid)
            clids = {x["lid"] for x in csched}
            plids = {x["lid"] for x in sched}
            foreign = [
                f"{s['start']}..{s['end']} lid={s['lid']}"
                for s in crows
                if s["lid"] is not None and s["lid"] not in clids
            ]
            check(
                not foreign,
                f"child {cid} IAD rows carry own installment ids (never the parent's)",
                "; ".join(foreign) or f"all {len(crows)} rows in child schedule",
            )
            cross = [s for s in crows if s["lid"] in plids and s["lid"] not in clids]
            check(not cross, f"child {cid} has no cross-loan installment FK", f"{len(cross)} rows")
            check(
                all(s["posted"] <= s["accrued"] for s in crows),
                f"child {cid} posted <= accrued",
                "ok",
            )
        check(
            child_total == parent_total,
            "SUM(children accrued) == parent accrued (window total)",
            f"children={child_total} parent={parent_total}",
        )

        # K2 — per-SEGMENT parity. The window total above can net to zero while
        # each individual month-end/due segment is off: on the fixture that
        # exposed this, parent 306/702 vs children 307/701 summed to 1008 on
        # both sides, so a window-only check reported PASS while every
        # month-end cut carried a rupee break.
        print("→ K2. per-segment parent vs children parity")
        child_segs: dict[tuple[date, date], Decimal] = {}
        for cid in loan["child_ids"]:
            for s in iad_rows(cid):
                k = (s["start"], s["end"])
                child_segs[k] = child_segs.get(k, Decimal(0)) + s["accrued"]
        for s in segs:
            k = (s["start"], s["end"])
            got = child_segs.get(k)
            check(
                got is not None and got == s["accrued"],
                f"segment {s['start']}..{s['end']} children sum == parent",
                f"children={got} parent={s['accrued']}"
                + ("" if got is None else f" delta={got - s['accrued']}"),
            )

        # K3 — each child's own ledger must reconcile to what billing bills it.
        print("→ K3. child accrued == child scheduled INT")
        for cid in loan["child_ids"]:
            crows = iad_rows(cid)
            for ins in schedule(cid):
                if not (start <= ins["due_date"] <= end):
                    continue
                got = sum((s["accrued"] for s in crows if s["lid"] == ins["lid"]), Decimal(0))
                check(
                    got == ins["int_due"],
                    f"child {cid} lid={ins['lid']} accrued == scheduled INT",
                    f"accrued={got} scheduled={ins['int_due']} delta={got - ins['int_due']}",
                )

    print(
        "  LAYERS_DECLARE: jobs=REAL(interestAccrualCalculation,interestAccrualPosting,"
        "loanAccountBillingJob) quarantine=REAL fixture=FRESH_DISBURSED asserts=DB_VALUE_LEVEL"
    )
    if FAILURES:
        print(f"=== FAIL: flowtest.fresh_loan_int_accrual_e2e ({len(FAILURES)} assert(s)) ===")
        for f in FAILURES:
            print(f"  - {f}")
        return 1
    print("=== PASS: flowtest.fresh_loan_int_accrual_e2e ===")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — harness boundary
        print(f"=== FAIL: flowtest.fresh_loan_int_accrual_e2e: {exc} ===")
        raise
