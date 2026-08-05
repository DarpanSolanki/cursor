"""Universal money invariants — run after EVERY scenario (not selectable).

TRUE-TO-WORLD R0 / TDPQA-72 392164 class:
  Per-txn partition D==C (assert_gl_balanced_txn) does NOT catch product-GL
  AIR/BI imbalance when force-bill BILLING + INTEREST bind outside LAN-scoped
  transaction_details and LOAN_PREPAYMENT still posts BPI_AMT.

Baseline-delta: snapshot at scenario start; only NEW violations fail the run.
"""
from __future__ import annotations

import json
import os
from decimal import Decimal
from typing import Any

from .asserts import ACCEPTANCE_STRICT
from .db import psql, psql_raw

INVARIANTS_OFF = os.environ.get("FLOWTEST_INVARIANTS", "1") == "0"
TOL = Decimal("0.01")

# loan_status → allowed account.status (platform pairs observed locally / state machine)
_LEGAL_STATUS: dict[str, set[str]] = {
    "ACTIVE": {"ACTIVE", "OPEN"},
    "CLOSED": {"CLOSED", "INACTIVE"},
    "WRITTEN_OFF": {"CLOSED", "WRITTEN_OFF", "INACTIVE"},
    "FORECLOSED": {"CLOSED", "INACTIVE"},
    "CANCELLED": {"CANCELLED", "CLOSED", "INACTIVE"},
}


def _dec(v: str | None) -> Decimal:
    return Decimal(v or "0")


def all_success_txn_refs(lan: str) -> list[str]:
    """LAN SUCCESS refs: transaction_details ∪ labd ∪ force-bill CRN shape."""
    raw = psql_raw(
        f"""
SELECT DISTINCT ref FROM (
  SELECT tm.reference_number AS ref
  FROM mfi_accounting.transaction_details td
  JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_id
  WHERE td.account_number = '{lan}' AND tm.reversed = false AND tm.status = 'SUCCESS'
  UNION
  SELECT labd.transaction_reference_number
  FROM mfi_accounting.loan_account_billing_details labd
  JOIN mfi_accounting.loan_account la ON la.account_id = labd.account_id
  WHERE la.la_account_number = '{lan}'
    AND COALESCE(labd.reversed,false) = false
    AND labd.transaction_reference_number IS NOT NULL
) u WHERE ref IS NOT NULL AND ref <> ''
ORDER BY 1;
"""
    ).strip()
    refs = {r.strip() for r in raw.splitlines() if r.strip()}
    fb = psql(
        f"""
SELECT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.la_account_number = '{lan}'
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ ('^' || la.account_id::text || '17[0-9]{{11}}([0-9]+)?$')
  AND tm.reversed = false AND tm.status = 'SUCCESS'
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    if fb:
        refs.add(fb.strip())
    return sorted(refs)


def scope_gl_totals(refs: list[str]) -> tuple[Decimal, Decimal]:
    if not refs:
        return Decimal("0"), Decimal("0")
    in_list = ",".join(f"'{r}'" for r in refs)
    row = psql(
        f"""
SELECT
  COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('D','DEBIT') THEN tpd.amount ELSE 0 END),0)::text,
  COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('C','CREDIT') THEN tpd.amount ELSE 0 END),0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
WHERE tm.reference_number IN ({in_list})
  AND tm.reversed = false AND tm.status = 'SUCCESS';
"""
    )
    a, b = (row or "0|0").split("|", 1)
    return _dec(a), _dec(b)


def per_ref_gl_imbalances(refs: list[str], *, tol: Decimal = TOL) -> dict[str, Decimal]:
    """Set-based per-txn |D−C| — one query for all refs (W1 perf)."""
    if not refs:
        return {}
    in_list = ",".join(f"'{r}'" for r in refs)
    raw = psql_raw(
        f"""
SELECT tm.reference_number,
  ABS(
    COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('D','DEBIT') THEN tpd.amount ELSE 0 END),0)
    - COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('C','CREDIT') THEN tpd.amount ELSE 0 END),0)
  )::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
WHERE tm.reference_number IN ({in_list})
  AND tm.reversed = false AND tm.status = 'SUCCESS'
GROUP BY tm.reference_number
HAVING ABS(
  COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('D','DEBIT') THEN tpd.amount ELSE 0 END),0)
  - COALESCE(SUM(CASE WHEN UPPER(tpd.cr_dr_indicator) IN ('C','CREDIT') THEN tpd.amount ELSE 0 END),0)
) > {tol};
"""
    ).strip()
    out: dict[str, Decimal] = {}
    for line in raw.splitlines():
        if not line.strip() or "|" not in line:
            continue
        ref, imb = line.split("|", 1)
        out[ref.strip()] = _dec(imb)
    return out


def bpi_air_credit_after_force_bill(lan: str) -> Decimal:
    """TDPQA-72 392164 detector: LOAN_PREPAYMENT BPI_AMT crediting AIR after FB exists."""
    fb = psql(
        f"""
SELECT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.la_account_number = '{lan}'
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ ('^' || la.account_id::text || '17[0-9]{{11}}([0-9]+)?$')
  AND tm.reversed = false AND tm.status = 'SUCCESS'
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    if not fb:
        return Decimal("0")
    row = psql(
        f"""
SELECT COALESCE(SUM(tpd.amount),0)::text
FROM mfi_accounting.transaction_details td
JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_id
  AND tm.reversed = false AND tm.status = 'SUCCESS'
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
WHERE td.account_number = '{lan}'
  AND tc.type = 'LOAN_PREPAYMENT'
  AND tpd.cr_dr_indicator = 'C'
  AND tpd.gl_code IN ('13578','CG13578')
  AND COALESCE(tpd.reference_code,'') = 'BPI_AMT';
"""
    )
    return _dec(row)


def fc_settlement_air_delta(lan: str) -> tuple[Decimal, list[str]]:
    """AIR D−C on FC settle bundle {force-bill, LOAN_PREPAYMENT, INTEREST≈fb amt}."""
    fb_row = psql(
        f"""
SELECT tm.reference_number||'|'||COALESCE(tm.original_amount,0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
JOIN mfi_accounting.loan_account la ON la.la_account_number = '{lan}'
WHERE tc.type = 'BILLING' AND tc.sub_type = 'NORMAL_BILLING'
  AND tm.client_reference_number ~ ('^' || la.account_id::text || '17[0-9]{{11}}([0-9]+)?$')
  AND tm.reversed = false AND tm.status = 'SUCCESS'
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    if not fb_row:
        return Decimal("0"), []
    fb_ref, amt_s = fb_row.split("|", 1)
    refs = [fb_ref.strip()]
    fb_amt = _dec(amt_s)
    lp = psql(
        f"""
SELECT tm.reference_number
FROM mfi_accounting.transaction_details td
JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_id
  AND tm.reversed = false AND tm.status = 'SUCCESS'
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
WHERE td.account_number = '{lan}' AND tc.type = 'LOAN_PREPAYMENT'
ORDER BY tm.id DESC LIMIT 1;
"""
    )
    if lp:
        refs.append(lp.strip())
    if fb_amt > 0:
        acc = psql_raw(
            f"""
SELECT tm.reference_number
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tm.transaction_catalogue_id
  AND tc.type = 'INTEREST'
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
  AND tpd.gl_code IN ('13578','CG13578') AND tpd.cr_dr_indicator = 'D'
  AND tpd.amount = {fb_amt}
WHERE tm.reversed = false AND tm.status = 'SUCCESS'
GROUP BY tm.reference_number, tm.id
ORDER BY tm.id DESC LIMIT 1;
"""
        ).strip()
        if acc:
            refs.append(acc.splitlines()[0].strip())
    in_list = ",".join(f"'{r}'" for r in refs)
    row = psql(
        f"""
SELECT
  COALESCE(SUM(CASE WHEN tpd.gl_code IN ('13578','CG13578') AND tpd.cr_dr_indicator='D'
    THEN tpd.amount ELSE 0 END),0)::text,
  COALESCE(SUM(CASE WHEN tpd.gl_code IN ('13578','CG13578') AND tpd.cr_dr_indicator='C'
    THEN tpd.amount ELSE 0 END),0)::text
FROM mfi_accounting.transaction_master tm
JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_id = tm.id
WHERE tm.reference_number IN ({in_list})
  AND tm.reversed = false AND tm.status = 'SUCCESS';
"""
    )
    d, c = (row or "0|0").split("|", 1)
    return abs(_dec(d) - _dec(c)), refs


def snapshot_invariants(lans: list[str]) -> dict[str, Any]:
    """Capture invariant state at scenario start (baseline for delta)."""
    out: dict[str, Any] = {"lans": {}, "ts": __import__("time").time()}
    for lan in lans:
        if not lan:
            continue
        refs = all_success_txn_refs(lan)
        d, c = scope_gl_totals(refs)
        unbalanced = sorted(per_ref_gl_imbalances(refs).keys())
        air_delta, _ = fc_settlement_air_delta(lan)
        bpi = bpi_air_credit_after_force_bill(lan)
        row = psql(
            f"""
SELECT la.loan_status,
       COALESCE(a.status,''),
       COALESCE(la.excess_amount,0)::text
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.la_account_number = '{lan}' AND la.is_deleted = false;
"""
        )
        ls, ast, ex = (row or "|||").split("|", 2) if row else ("", "", "0")
        neg_dues = psql(
            f"""
SELECT COUNT(*)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = '{lan}' AND ldd.is_deleted = false
  AND (ldd.due_amount < 0 OR ldd.paid_amount < 0 OR ldd.waived_amount < 0);
"""
        )
        orphan = psql(
            f"""
SELECT COUNT(*)::text
FROM mfi_accounting.loan_due_details ldd
JOIN mfi_accounting.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = '{lan}' AND ldd.is_deleted = false
  AND ldd.loan_installment_details_id IS NOT NULL
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.loan_installment_details lid
    WHERE lid.id = ldd.loan_installment_details_id AND lid.is_deleted = false
  );
"""
        )
        out["lans"][lan] = {
            "gl_imbalance": abs(d - c),
            "unbalanced_refs": unbalanced,
            "ref_count": len(refs),
            "air_delta": air_delta,
            "bpi_air": bpi,
            "loan_status": ls,
            "account_status": ast,
            "excess": _dec(ex),
            "neg_dues": int(neg_dues or "0"),
            "orphan_dues": int(orphan or "0"),
        }
    return out


def _new_violation(base: Decimal | int, now: Decimal | int, *, tol: Decimal = TOL) -> bool:
    if isinstance(base, int) and isinstance(now, int):
        return now > base
    return _dec(str(now)) > _dec(str(base)) + tol


def run_universal_invariants(
    lans: list[str],
    *,
    baseline: dict[str, Any] | None = None,
    label: str = "post-scenario",
    absolute_only: bool = False,
) -> dict[str, Any]:
    """Fail-closed universal layer. Returns verdict dict; raises AssertionError on NEW violation.

    absolute_only=True asserts only invariants that must hold in ANY state (per-txn
    double-entry, negative/orphan dues, status legality, negative excess) and skips the
    bundle/scope deltas that legitimately differ while a LAN sits mid-flow. Use it when
    there is no genuine before-baseline — a self-snapshot baseline neutralises every
    delta check and makes the gate vacuous.
    """
    if INVARIANTS_OFF:
        print(f"  invariants SKIP: FLOWTEST_INVARIANTS=0 ({label})")
        return {"skipped": True, "label": label}
    if not ACCEPTANCE_STRICT:
        print(f"  invariants SKIP: ACCEPTANCE_STRICT=0 ({label})")
        return {"skipped": True, "label": label}

    lans = [x for x in lans if x]
    if not lans:
        print(f"  invariants SKIP: no LANs ({label})")
        return {"skipped": True, "label": label}

    base = (baseline or {}).get("lans") or {}
    now = snapshot_invariants(lans)
    failures: list[str] = []
    verdicts: list[dict[str, Any]] = []

    for lan in lans:
        b = base.get(lan) or {
            "gl_imbalance": Decimal("0"),
            "unbalanced_refs": [],
            "air_delta": Decimal("0"),
            "bpi_air": Decimal("0"),
            "neg_dues": 0,
            "orphan_dues": 0,
            "excess": Decimal("0"),
        }
        n = now["lans"][lan]
        refs = all_success_txn_refs(lan)
        base_unbal = set(b.get("unbalanced_refs") or [])
        imb_map = per_ref_gl_imbalances(refs)
        # (a) per-txn — only NEW unbalanced refs fail (baseline-delta)
        for ref, imb in imb_map.items():
            if ref not in base_unbal:
                failures.append(
                    f"inv GL per-txn FAIL {lan} ref={ref}: |D-C|={imb}"
                )
        d, c = scope_gl_totals(refs)
        scope_imb = abs(d - c)
        if not absolute_only and scope_imb > TOL and _new_violation(_dec(str(b.get("gl_imbalance", 0))), scope_imb):
            failures.append(
                f"inv GL whole-scope FAIL {lan}: debit={d} credit={c} diff={scope_imb} "
                f"refs={len(refs)} (baseline_imb={b.get('gl_imbalance')})"
            )
        # product AIR (392164) — only when force-bill present in current state
        air_delta, air_refs = fc_settlement_air_delta(lan)
        bpi = bpi_air_credit_after_force_bill(lan)
        if not absolute_only and bpi > TOL and _new_violation(_dec(str(b.get("bpi_air", 0))), bpi):
            failures.append(
                f"inv BPI-after-FB FAIL {lan}: LOAN_PREPAYMENT BPI_AMT AIR credit={bpi} "
                f"(TDPQA-72 392164 class; baseline={b.get('bpi_air')})"
            )
        if not absolute_only and air_delta > TOL and _new_violation(_dec(str(b.get("air_delta", 0))), air_delta):
            failures.append(
                f"inv FC settlement AIR FAIL {lan}: |D-C|={air_delta} refs={air_refs} "
                f"(product GL; baseline={b.get('air_delta')})"
            )
        # (b) dues ↔ schedule
        if n["orphan_dues"] > int(b.get("orphan_dues") or 0):
            failures.append(
                f"inv dues↔schedule FAIL {lan}: orphan_dues={n['orphan_dues']} "
                f"(baseline={b.get('orphan_dues')})"
            )
        if n["neg_dues"] > int(b.get("neg_dues") or 0):
            failures.append(
                f"inv negative-dues FAIL {lan}: neg_dues={n['neg_dues']}"
            )
        # (c) status legality
        ls, ast = n["loan_status"], n["account_status"]
        allowed = _LEGAL_STATUS.get(ls)
        if ls and allowed is not None and ast and ast not in allowed:
            if not base.get(lan) or (b.get("loan_status"), b.get("account_status")) != (ls, ast):
                failures.append(
                    f"inv status FAIL {lan}: loan_status={ls!r} account.status={ast!r} "
                    f"allowed={sorted(allowed)}"
                )
        # (d) no negative excess
        if n["excess"] < -TOL and (
            not base.get(lan) or _dec(str(b.get("excess", 0))) >= -TOL
        ):
            failures.append(f"inv excess FAIL {lan}: excess={n['excess']}")

        verdicts.append(
            {
                "lan": lan,
                "refs": len(refs),
                "scope_d": str(d),
                "scope_c": str(c),
                "air_delta": str(air_delta),
                "bpi_air": str(bpi),
                "loan_status": ls,
                "account_status": ast,
                "ok": True,  # filled after failures scan
            }
        )
        print(
            f"  invariants {label}: {lan} refs={len(refs)} scope_D={d} C={c} "
            f"air_delta={air_delta} bpi_air={bpi} status={ls}/{ast}"
        )

    for v in verdicts:
        v["ok"] = not any(v["lan"] in f for f in failures)

    result = {
        "label": label,
        "verdicts": verdicts,
        "failures": failures,
        "now": now,
        "ok": not failures,
    }
    if failures:
        msg = " | ".join(failures[:5])
        raise AssertionError(f"UNIVERSAL INVARIANTS FAIL ({label}): {msg}")
    print(f"  invariants PASS: {label} lans={lans}")
    return result


def lans_from_ctx(ctx: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for k in ("parent_lan", "child_lan", "child1_lan", "child2_lan", "lan"):
        v = ctx.get(k)
        if v and v not in out:
            out.append(str(v))
    for k in ("children", "lans", "all_lans"):
        v = ctx.get(k)
        if isinstance(v, (list, tuple)):
            for x in v:
                if x and str(x) not in out:
                    out.append(str(x))
    return out


def finish_scenario(lans: list[str], *, baseline: dict[str, Any] | None, label: str) -> None:
    """Call at end of every standalone scenario (runner already does this)."""
    run_universal_invariants(lans, baseline=baseline, label=label)
