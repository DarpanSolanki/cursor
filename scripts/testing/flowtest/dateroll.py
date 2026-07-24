"""Owned business-date progression via real HTTP batch fire + mfi_batch poll.

Batch order verified from `.cursor/skills/accounting-knowledge/batchnew-jobs.md`
(Interest → Penal → Billing → DPD → Asset criteria → Asset classification) and
confirmed against local `mfi_batch.batch_job_instance.job_name` strings.

Synthetic `--job-time` (IST EOD ms) drives as-of processing — same pattern as
DCF SEED_EXTRA / `create_fresh_dcf_group_fixture.sync_billing_for_group`.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))

from clb_queue_harness import (  # noqa: E402
    quarantine_billing_portfolio,
    restore_billing_portfolio_quarantine,
)

from .runner import fire_batch, max_batch_execution_id, wait_batch  # noqa: E402

IST = ZoneInfo("Asia/Kolkata")

# (apiName for api-fire, batch_job_instance.job_name) — verified order
CHAIN_EOD: tuple[tuple[str, str], ...] = (
    ("interestAccrualCalculation", "interestAccrualCalculation"),
    ("interestAccrualPosting", "interestAccrualPosting"),
    ("penalInterestAccrualCalculation", "penalInterestAccrualCalculation"),
    ("penalInterestAccrualBooking", "penalInterestAccrualBooking"),
    ("loanAccountBillingJob", "loanAccountBillingJob"),
    ("loanAccountDpdCalcJob", "loanAccountDpdCalcJob"),
    ("loanAccountAssetCriteriaJob", "loanAccountAssetCriteriaJob"),
    ("loanAccountAssetClassificationJob", "loanAccountAssetClassificationJob"),
)

# Sub-chains: keep dependency order; skip unrelated jobs for wall budget.
CHAIN_ACCRUAL_BILLING: tuple[tuple[str, str], ...] = (
    CHAIN_EOD[0],  # interestAccrualCalculation
    CHAIN_EOD[1],  # interestAccrualPosting
    CHAIN_EOD[4],  # loanAccountBillingJob
)
CHAIN_PENAL = CHAIN_EOD[2:4]  # penal calc → booking
CHAIN_DPD_NPA = CHAIN_EOD[5:8]  # dpd → criteria → classification


@dataclass
class RollResult:
    days: list[str]
    jobs_fired: list[tuple[str, str, str]]  # (day, api, job_time)
    layers_real: list[str]
    layers_seeded: list[str]


def eod_ms_ist(d: date | str) -> str:
    """Platform-style IST EOD epoch ms (matches DCF `_eod_ms` — 18:00 Asia/Kolkata)."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    dt = datetime(d.year, d.month, d.day, 18, 0, 0, tzinfo=IST)
    return str(int(dt.timestamp() * 1000))


def _daterange(start: date, end: date) -> list[date]:
    if end < start:
        raise ValueError(f"roll end {end} < start {start}")
    out: list[date] = []
    cur = start
    while cur <= end:
        out.append(cur)
        cur += timedelta(days=1)
    return out


def fire_and_wait(
    api: str,
    job_time: str,
    *,
    job_name: str | None = None,
    timeout_s: int = 90,
    soft_fail: bool = True,
) -> None:
    """HTTP fire one batch + poll mfi_batch past prior max execution id."""
    jn = job_name or api
    before = max_batch_execution_id(jn)
    fire_batch(api, job_time)
    try:
        wait_batch(jn, before, timeout_s=timeout_s)
    except RuntimeError as exc:
        if soft_fail:
            print(f"  WARN: {api}@{job_time}: {exc}")
        else:
            raise


def roll(
    start: date | str,
    end: date | str,
    *,
    chain: Sequence[tuple[str, str]] = CHAIN_EOD,
    quarantine_parent_id: int | None = None,
    quarantine_child_ids: Sequence[int] | None = None,
    timeout_s: int = 90,
    layers_seeded: Iterable[str] = (),
) -> RollResult:
    """Fire `chain` for each calendar day in [start, end] (inclusive).

    When quarantine_* set, portfolio is narrowed so EOD jobs only touch the
    fixture (DCF SEED_EXTRA pattern) — required to stay under wall budgets.
    """
    s = date.fromisoformat(start) if isinstance(start, str) else start
    e = date.fromisoformat(end) if isinstance(end, str) else end
    days = _daterange(s, e)
    fired: list[tuple[str, str, str]] = []
    layers_real = [api for api, _ in chain]

    q_parent = quarantine_parent_id
    q_children = list(quarantine_child_ids or [])
    try:
        if q_parent is not None:
            quarantine_billing_portfolio(int(q_parent), [int(x) for x in q_children])
            print(
                f"  dateroll quarantine parent={q_parent} "
                f"children={len(q_children)} days={len(days)} chain={len(chain)}"
            )
        for d in days:
            jt = eod_ms_ist(d)
            iso = d.isoformat()
            print(f"  dateroll day={iso} job_time={jt}")
            for api, jn in chain:
                fire_and_wait(api, jt, job_name=jn, timeout_s=timeout_s, soft_fail=True)
                fired.append((iso, api, jt))
    finally:
        if q_parent is not None:
            restore_billing_portfolio_quarantine()
            print("  dateroll quarantine restored")

    return RollResult(
        days=[d.isoformat() for d in days],
        jobs_fired=fired,
        layers_real=layers_real,
        layers_seeded=list(layers_seeded),
    )


def declare_layers(result: RollResult) -> None:
    """Fail-closed coverage label helper — print real vs seeded."""
    print(
        f"  LAYERS real={','.join(result.layers_real) or '-'} "
        f"seeded={','.join(result.layers_seeded) or '-'}"
    )
