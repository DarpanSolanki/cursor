-- SDCP-11012 QA1 single-loan L0 (LAN 6000196157 / parent 3641260).
-- Prefer bulk scripts for all SHG. This is ticket-scoped only.
-- Absorb parent−children accrued diff on last child 3641462 latest accrual row.
-- No updated_on/updated_by on dpi_accrual_details (those columns do not exist).

\set ON_ERROR_STOP on

WITH parent_total AS (
  SELECT COALESCE(SUM(total_accrued_amount), 0) AS amt
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = 3641260 AND is_deleted = false AND total_accrued_amount > 0
),
child_total AS (
  SELECT COALESCE(SUM(total_accrued_amount), 0) AS amt
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id IN (3641460, 3641461, 3641462)
    AND is_deleted = false AND total_accrued_amount > 0
),
diff AS (
  SELECT (p.amt - c.amt) AS d FROM parent_total p, child_total c
)
UPDATE mfi_accounting.dpi_accrual_details d
SET total_accrued_amount = d.total_accrued_amount + (SELECT d FROM diff)
WHERE d.id = (
  SELECT id
  FROM mfi_accounting.dpi_accrual_details
  WHERE loan_account_id = 3641462
    AND is_deleted = false
    AND total_accrued_amount > 0
  ORDER BY end_date DESC, id DESC
  LIMIT 1
)
AND (SELECT d FROM diff) <> 0
AND (SELECT d.total_accrued_amount + (SELECT d FROM diff)
     FROM mfi_accounting.dpi_accrual_details d
     WHERE d.loan_account_id = 3641462 AND d.is_deleted = false AND d.total_accrued_amount > 0
     ORDER BY end_date DESC, id DESC LIMIT 1) > 0;

-- Companion unpaid DPI LDD bump on last child latest unpaid bill (if outstanding still off)
WITH parent_os AS (
  SELECT COALESCE(SUM(GREATEST(due_amount - paid_amount - waived_amount, 0)), 0) AS amt
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id = 3641260 AND component_type = 'DPI' AND is_deleted = false
),
child_os AS (
  SELECT COALESCE(SUM(GREATEST(due_amount - paid_amount - waived_amount, 0)), 0) AS amt
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id IN (3641460, 3641461, 3641462)
    AND component_type = 'DPI' AND is_deleted = false
),
diff AS (
  SELECT (p.amt - c.amt) AS d FROM parent_os p, child_os c
)
UPDATE mfi_accounting.loan_due_details ldd
SET due_amount = ldd.due_amount + (SELECT d FROM diff),
    updated_on = NOW(),
    updated_by = 'SDCP-11012-repair'
WHERE ldd.id = (
  SELECT id
  FROM mfi_accounting.loan_due_details
  WHERE loan_account_id = 3641462
    AND component_type = 'DPI'
    AND is_deleted = false
    AND paid_amount = 0
    AND waived_amount = 0
    AND due_amount > 0
  ORDER BY due_date DESC, id DESC
  LIMIT 1
)
AND (SELECT d FROM diff) <> 0
AND ABS((SELECT d FROM diff)) <= 5;
