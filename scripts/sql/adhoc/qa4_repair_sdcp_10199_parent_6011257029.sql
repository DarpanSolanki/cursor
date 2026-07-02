-- SDCP-10199 QA4 repair: parent left with outstanding after last-child DFC (pre Fix-D build).
-- Child LAN 6011257534 was approved 2026-09-14; parent 6011257029 shows loan CLOSED but account ACTIVE
-- with PRIN/INT pending and unsettled installments.
--
-- Run on QA4 only after review. Matches DeathForeclosureInsuranceWriter Fix-D outcome:
--   waive all pending parent dues, settle installments, close account row.
--
-- psql ... -v ON_ERROR_STOP=1 -f scripts/sql/adhoc/qa4_repair_sdcp_10199_parent_6011257029.sql

\set parent_lan '6011257029'

BEGIN;
SET search_path TO mfi_accounting;

-- 1) Waive all pending parent loan_due_details
UPDATE loan_due_details ldd
SET
  waived_amount = COALESCE(ldd.waived_amount, 0)
    + (ldd.due_amount - COALESCE(ldd.paid_amount, 0) - COALESCE(ldd.waived_amount, 0)),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'SDCP_10199_QA4_REPAIR'
FROM loan_account la
WHERE la.account_id = ldd.loan_account_id
  AND la.la_account_number = :'parent_lan'
  AND ldd.is_deleted = false
  AND ldd.due_amount > COALESCE(ldd.paid_amount, 0) + COALESCE(ldd.waived_amount, 0);

-- 2) Settle all parent installments (paid banner + hide next EMI)
UPDATE loan_installment_details lid
SET
  is_settled = true,
  settled_amount = COALESCE(lid.installment_amount, 0),
  last_paid_date = COALESCE(lid.last_paid_date, CURRENT_TIMESTAMP),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'SDCP_10199_QA4_REPAIR'
FROM loan_account la
WHERE la.account_id = lid.loan_account_id
  AND la.la_account_number = :'parent_lan'
  AND lid.is_deleted = false
  AND lid.is_settled = false;

-- 3) Close account row (loan already CLOSED)
UPDATE account a
SET
  status = 'CLOSED',
  closing_date = COALESCE(a.closing_date, la.la_closing_date, CURRENT_TIMESTAMP),
  updated_on = CURRENT_TIMESTAMP,
  updated_by = 'SDCP_10199_QA4_REPAIR'
FROM loan_account la
WHERE la.account_id = a.id
  AND la.la_account_number = :'parent_lan'
  AND a.is_deleted = false;

COMMIT;

-- Verify
SELECT la.la_account_number, la.loan_status, a.status AS account_status, la.excess_amount
FROM loan_account la
JOIN account a ON a.id = la.account_id
WHERE la.la_account_number = :'parent_lan';

SELECT component_type,
       ROUND(SUM(due_amount - COALESCE(paid_amount,0) - COALESCE(waived_amount,0))::numeric, 2) AS pending
FROM loan_due_details ldd
JOIN loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.la_account_number = :'parent_lan' AND ldd.is_deleted = false
GROUP BY component_type
HAVING SUM(due_amount - COALESCE(paid_amount,0) - COALESCE(waived_amount,0)) > 0.01;

SELECT COUNT(*) FILTER (WHERE NOT is_settled) AS unsettled,
       COUNT(*) FILTER (WHERE is_settled) AS settled
FROM loan_installment_details lid
JOIN loan_account la ON la.account_id = lid.loan_account_id
WHERE la.la_account_number = :'parent_lan' AND lid.is_deleted = false;
