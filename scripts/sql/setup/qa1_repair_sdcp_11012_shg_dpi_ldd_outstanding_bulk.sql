-- SDCP-11012 — QA1 L0 companion: align unpaid DPI loan_due_details outstanding
-- after accrual repair when bills already exist.
-- Absorbs outstanding diff on last child's latest unpaid DPI due row (paid=0, waived=0).
-- Scope: ABS(outstanding_diff) <= 5 and both sides have unpaid DPI dues.
-- Does NOT change paid/waived amounts. Does NOT reverse GL (credit risk: screen parity only).
--
-- PRE: accrual bulk repair already applied; re-audit outstanding mismatch.
-- POST: parent unpaid DPI outstanding == sum(children unpaid DPI outstanding) for ROUNDING set.

\set ON_ERROR_STOP on
BEGIN;

CREATE TEMP TABLE _sdcp11012_ldd_fixes ON COMMIT DROP AS
WITH parents AS (
  SELECT account_id
  FROM mfi_accounting.loan_account
  WHERE has_child_accounts = true
    AND parent_loan_account_id IS NULL
    AND loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
    AND COALESCE(is_deleted, false) = false
),
parent_os AS (
  SELECT p.account_id,
         COALESCE(SUM(GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)), 0) AS parent_os
  FROM parents p
  LEFT JOIN mfi_accounting.loan_due_details ldd
    ON ldd.loan_account_id = p.account_id
   AND ldd.component_type = 'DPI'
   AND ldd.is_deleted = false
  GROUP BY p.account_id
),
child_os AS (
  SELECT c.parent_loan_account_id AS account_id,
         COALESCE(SUM(GREATEST(ldd.due_amount - ldd.paid_amount - ldd.waived_amount, 0)), 0) AS children_os
  FROM mfi_accounting.loan_account c
  JOIN parents p ON p.account_id = c.parent_loan_account_id
  LEFT JOIN mfi_accounting.loan_due_details ldd
    ON ldd.loan_account_id = c.account_id
   AND ldd.component_type = 'DPI'
   AND ldd.is_deleted = false
  WHERE COALESCE(c.is_deleted, false) = false
  GROUP BY c.parent_loan_account_id
),
targets AS (
  SELECT po.account_id AS parent_id,
         (po.parent_os - co.children_os) AS diff
  FROM parent_os po
  JOIN child_os co ON co.account_id = po.account_id
  WHERE po.parent_os > 0
    AND co.children_os > 0
    AND po.parent_os <> co.children_os
    AND ABS(po.parent_os - co.children_os) <= 5
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
last_ldd AS (
  SELECT DISTINCT ON (lc.parent_id)
         lc.parent_id,
         lc.last_child_id,
         ldd.id AS ldd_id,
         ldd.due_amount AS before_due,
         t.diff
  FROM last_child lc
  JOIN targets t ON t.parent_id = lc.parent_id
  JOIN mfi_accounting.loan_due_details ldd
    ON ldd.loan_account_id = lc.last_child_id
   AND ldd.component_type = 'DPI'
   AND ldd.is_deleted = false
   AND ldd.paid_amount = 0
   AND ldd.waived_amount = 0
   AND ldd.due_amount > 0
  ORDER BY lc.parent_id, ldd.due_date DESC, ldd.id DESC
)
SELECT parent_id, last_child_id, ldd_id, before_due, diff,
       before_due + diff AS after_due
FROM last_ldd
WHERE before_due + diff > 0;

SELECT COUNT(*) AS ldd_rows_to_update, COALESCE(SUM(ABS(diff)), 0) AS total_abs_diff
FROM _sdcp11012_ldd_fixes;

UPDATE mfi_accounting.loan_due_details ldd
SET due_amount = f.after_due,
    updated_on = NOW(),
    updated_by = 'SDCP-11012-repair'
FROM _sdcp11012_ldd_fixes f
WHERE ldd.id = f.ldd_id;

SELECT parent_id, last_child_id, ldd_id, before_due, diff, after_due
FROM _sdcp11012_ldd_fixes
ORDER BY parent_id
LIMIT 20;

COMMIT;
