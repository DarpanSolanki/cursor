"""Shared loan_account state hygiene for flowtest scenarios.

NPA→regular slab reset (F2 repayment path) lives here so accrual/DPD/NPA
scenarios do not fork the same SQL.
"""
from __future__ import annotations

from .db import psql, psql_multi


def force_regular_asset_slab(account_ids: list[int | str]) -> None:
    """Reset NPA tagging so CASH postTransaction does not take NPA PTC.

    Proven on F2 repayment_reversal (product-70 local 134207 without this).
    """
    ids = [int(a) for a in account_ids if str(a).strip()]
    if not ids:
        return
    for account_id in ids:
        psql_multi(
            f"""
UPDATE mfi_accounting.loan_account la
SET asset_criteria_slabs_id = sub.regular_slab,
    npa_tagging_date = NULL,
    npa_ageing_start_date = NULL,
    sec_npa_tagging_date = NULL,
    is_sec_npa = false,
    past_due_days = 0,
    updated_on = NOW(),
    updated_by = 'FLOWTEST_NPA_HYGIENE'
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
"""
        )
    print(f"  hygiene: force REGULAR slab on accounts={ids}")


def age_dues_for_dpd(
    account_id: int,
    *,
    as_of: str,
    min_dpd_days: int = 90,
) -> dict:
    """Lazy aging: backdate unpaid installment + open dues so DPD≥min_dpd_days.

    Coverage must label aging=SEEDED; only subsequent batch jobs are REAL.
    """
    from datetime import date, timedelta

    as_of_d = date.fromisoformat(as_of)
    target_due = (as_of_d - timedelta(days=min_dpd_days)).isoformat()
    row = psql(
        f"""
        SELECT id::text || '|' || installment_date::date::text
        FROM mfi_accounting.loan_installment_details
        WHERE loan_account_id={int(account_id)}
          AND COALESCE(is_deleted,false)=false
          AND COALESCE(settled_amount,0) < COALESCE(installment_amount,0)
        ORDER BY installment_date ASC NULLS LAST, id ASC
        LIMIT 1
        """
    )
    if not row or "|" not in row:
        raise RuntimeError(f"no unpaid installment to age for account={account_id}")
    lid, old_inst = row.split("|", 1)
    psql_multi(
        f"""
        UPDATE mfi_accounting.loan_installment_details
        SET installment_date='{target_due}'::timestamp,
            overdue_date='{target_due}'::timestamp,
            updated_on=NOW(),
            updated_by='FLOWTEST_DPD_AGE'
        WHERE id={int(lid)};

        UPDATE mfi_accounting.loan_due_details
        SET due_date='{target_due}'::timestamp,
            updated_on=NOW(),
            updated_by='FLOWTEST_DPD_AGE'
        WHERE loan_account_id={int(account_id)}
          AND COALESCE(is_deleted,false)=false
          AND (due_amount - COALESCE(paid_amount,0) - COALESCE(waived_amount,0)) > 0
          AND loan_installment_details_id={int(lid)};
        """
    )
    print(
        f"  hygiene: age dues account={account_id} lid={lid} "
        f"{old_inst}→{target_due} (SEEDED dpd≥{min_dpd_days})"
    )
    return {
        "lid": lid,
        "old_installment_date": old_inst,
        "target_due": target_due,
        "as_of": as_of,
        "min_dpd_days": min_dpd_days,
    }
