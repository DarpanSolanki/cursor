-- SDCP-11012 — QA1 L0 bulk repair for SHG DPI accrual ROUNDING drifts only.
-- Pattern mirrors InterestAccrualBookingService last-child absorb:
--   last active child latest dpi_accrual_details.total_accrued_amount += (parent - sum(children)).
-- Scope: ABS(diff) <= 5 AND both parent and child accruals > 0.
-- Does NOT touch STRUCTURAL / ONE_SIDE_ZERO parents (needs calc rewind / RCA).
-- Does NOT reverse GL. If DPI already billed to loan_due_details, run companion LDD script after this.
--
-- PRE: run qa1_sdcp_11012_shg_dpi_audit.sql and review ROUNDING count (~89 on QA1 snapshot).
-- POST: re-run audit; ROUNDING count must be 0.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE _sdcp11012_accrual_fixes ON COMMIT DROP AS
WITH parents AS (
  SELECT account_id
  FROM mfi_accounting.loan_account
  WHERE has_child_accounts = true
    AND parent_loan_account_id IS NULL
    AND loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
    AND COALESCE(is_deleted, false) = false
),
parent_dpi AS (
  SELECT p.account_id, COALESCE(SUM(d.total_accrued_amount), 0) AS parent_accrued
  FROM parents p
  LEFT JOIN mfi_accounting.dpi_accrual_details d
    ON d.loan_account_id = p.account_id
   AND d.is_deleted = false
   AND d.total_accrued_amount > 0
  GROUP BY p.account_id
),
child_dpi AS (
  SELECT c.parent_loan_account_id AS account_id,
         COALESCE(SUM(d.total_accrued_amount), 0) AS children_accrued
  FROM mfi_accounting.loan_account c
  JOIN parents p ON p.account_id = c.parent_loan_account_id
  LEFT JOIN mfi_accounting.dpi_accrual_details d
    ON d.loan_account_id = c.account_id
   AND d.is_deleted = false
   AND d.total_accrued_amount > 0
  WHERE COALESCE(c.is_deleted, false) = false
  GROUP BY c.parent_loan_account_id
),
targets AS (
  SELECT pd.account_id AS parent_id,
         (pd.parent_accrued - cd.children_accrued) AS diff
  FROM parent_dpi pd
  JOIN child_dpi cd ON cd.account_id = pd.account_id
  WHERE pd.parent_accrued > 0
    AND cd.children_accrued > 0
    AND pd.parent_accrued <> cd.children_accrued
    AND ABS(pd.parent_accrued - cd.children_accrued) <= 5
),
last_child AS (
  SELECT DISTINCT ON (c.parent_loan_account_id)
         c.parent_loan_account_id AS parent_id,
         c.account_id AS last_child_id
  FROM mfi_accounting.loan_account c
  JOIN targets t ON t.parent_id = c.parent_loan_account_id
  WHERE COALESCE(c.is_deleted, false) = false
    AND c.loan_status <> 'CLOSED'
  ORDER BY c.parent_loan_account_id, c.account_id DESC
),
last_row AS (
  SELECT DISTINCT ON (lc.parent_id)
         lc.parent_id,
         lc.last_child_id,
         d.id AS dpi_row_id,
         d.total_accrued_amount AS before_amt,
         t.diff
  FROM last_child lc
  JOIN targets t ON t.parent_id = lc.parent_id
  JOIN mfi_accounting.dpi_accrual_details d
    ON d.loan_account_id = lc.last_child_id
   AND d.is_deleted = false
   AND d.total_accrued_amount > 0
  ORDER BY lc.parent_id, d.end_date DESC, d.id DESC
)
SELECT parent_id, last_child_id, dpi_row_id, before_amt, diff,
       before_amt + diff AS after_amt
FROM last_row
WHERE before_amt + diff > 0;

SELECT COUNT(*) AS rows_to_update, COALESCE(SUM(ABS(diff)), 0) AS total_abs_diff
FROM _sdcp11012_accrual_fixes;

UPDATE mfi_accounting.dpi_accrual_details d
SET total_accrued_amount = f.after_amt
FROM _sdcp11012_accrual_fixes f
WHERE d.id = f.dpi_row_id;

SELECT parent_id, last_child_id, dpi_row_id, before_amt, diff, after_amt
FROM _sdcp11012_accrual_fixes
ORDER BY parent_id
LIMIT 20;

COMMIT;
