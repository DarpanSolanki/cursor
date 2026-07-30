-- SHG parent vs ACTIVE children INT Accrued parity (installment-window = distribute SoT).
-- Bounds match InterestGroupLoanAccrualDistributionService: as_of=MAX(parent IAD end),
-- prev=previous installment before as_of, next=today-or-next due on as_of.
-- Usage:
--   bash scripts/db-local.sh --sql "$(sed \"s/:parent_lan/'6000000832'/\" scripts/sql/helpers/verify_shg_interest_accrual_parity.sql)"

WITH p AS (
  SELECT la.account_id
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
  WHERE a.account_number = :parent_lan
),
asof AS (
  SELECT COALESCE(
    (SELECT MAX(end_date) FROM mfi_accounting.interest_accrual_details iad WHERE iad.account_id = (SELECT account_id FROM p)),
    CURRENT_DATE::timestamp
  ) AS as_of
),
win AS (
  SELECT
    COALESCE(
      (SELECT MAX(lid.installment_date)
         FROM mfi_accounting.loan_installment_details lid
        WHERE lid.loan_account_id = (SELECT account_id FROM p)
          AND COALESCE(lid.is_deleted, false) = false
          AND lid.installment_date < (SELECT as_of FROM asof)),
      (SELECT la.expected_disbursement_date FROM mfi_accounting.loan_account la WHERE la.account_id = (SELECT account_id FROM p))
    ) AS prev_due,
    (SELECT MIN(ldd.due_date)
       FROM mfi_accounting.loan_due_details ldd
      WHERE ldd.loan_account_id = (SELECT account_id FROM p)
        AND COALESCE(ldd.is_deleted, false) = false
        AND ldd.due_date >= (SELECT as_of FROM asof)::date) AS next_due
),
parent_acc AS (
  SELECT COALESCE(SUM(iad.total_accrued_amount), 0) AS accrued,
         COALESCE(SUM(iad.total_accrual_posted_amount), 0) AS posted
  FROM mfi_accounting.interest_accrual_details iad, win
  WHERE iad.account_id = (SELECT account_id FROM p)
    AND iad.end_date > win.prev_due
    AND iad.end_date <= win.next_due
),
child_acc AS (
  SELECT COALESCE(SUM(iad.total_accrued_amount), 0) AS accrued,
         COALESCE(SUM(iad.total_accrual_posted_amount), 0) AS posted
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.interest_accrual_details iad ON iad.account_id = la.account_id
  CROSS JOIN win
  WHERE la.parent_loan_account_id = (SELECT account_id FROM p)
    AND la.loan_status = 'ACTIVE'
    AND iad.end_date > win.prev_due
    AND iad.end_date <= COALESCE(win.next_due, DATE '9999-12-31')
)
SELECT
  (SELECT prev_due FROM win) AS prev_due,
  (SELECT next_due FROM win) AS next_due,
  (SELECT accrued FROM parent_acc) AS parent_window_accrued,
  (SELECT accrued FROM child_acc) AS children_window_sum,
  (SELECT accrued FROM parent_acc) - (SELECT accrued FROM child_acc) AS diff,
  CASE
    WHEN (SELECT next_due FROM win) IS NULL THEN 'SKIP_NO_NEXT_DUE'
    WHEN (SELECT accrued FROM parent_acc) = (SELECT accrued FROM child_acc) THEN 'PASS'
    WHEN (SELECT accrued FROM child_acc) > (SELECT accrued FROM parent_acc)
     AND (SELECT posted FROM child_acc) > 0 THEN 'PASS_POSTED_FLOOR'
    ELSE 'FAIL'
  END AS verdict;
