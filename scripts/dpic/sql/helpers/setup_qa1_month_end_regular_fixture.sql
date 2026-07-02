-- Regular (non-NPA) loan + 2nd-of-month EMI — same calendar shape as QA1 6801460 without NPA tagging.
\set ON_ERROR_STOP on

BEGIN;

CREATE TABLE IF NOT EXISTS mfi_accounting._qa1_month_end_regular_backup (
  loan_account_id           BIGINT NOT NULL,
  entity_kind               TEXT NOT NULL,
  entity_id                 BIGINT NOT NULL,
  installment_date          TIMESTAMP,
  overdue_date              TIMESTAMP,
  due_date                  TIMESTAMP,
  npa_ageing_start_date     TIMESTAMP,
  npa_tagging_date          TIMESTAMP,
  backed_up_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (loan_account_id, entity_kind, entity_id)
);

INSERT INTO mfi_accounting._qa1_month_end_regular_backup (
  loan_account_id, entity_kind, entity_id, npa_ageing_start_date, npa_tagging_date
)
SELECT la.account_id, 'loan_account', la.account_id, la.npa_ageing_start_date, la.npa_tagging_date
FROM mfi_accounting.loan_account la
WHERE la.account_id = :loan_account_id::bigint
ON CONFLICT (loan_account_id, entity_kind, entity_id) DO UPDATE SET
  npa_ageing_start_date = EXCLUDED.npa_ageing_start_date,
  npa_tagging_date = EXCLUDED.npa_tagging_date,
  backed_up_at = NOW();

INSERT INTO mfi_accounting._qa1_month_end_regular_backup (
  loan_account_id, entity_kind, entity_id, installment_date, overdue_date
)
SELECT lid.loan_account_id, 'installment', lid.id, lid.installment_date, lid.overdue_date
FROM mfi_accounting.loan_installment_details lid
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number IN (6, 7, 8)
ON CONFLICT (loan_account_id, entity_kind, entity_id) DO UPDATE SET
  installment_date = EXCLUDED.installment_date,
  overdue_date = EXCLUDED.overdue_date,
  backed_up_at = NOW();

INSERT INTO mfi_accounting._qa1_month_end_regular_backup (
  loan_account_id, entity_kind, entity_id, due_date
)
SELECT ldd.loan_account_id, 'due', ldd.id, ldd.due_date
FROM mfi_accounting.loan_due_details ldd
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.loan_installment_details_id IN (
    SELECT id FROM mfi_accounting.loan_installment_details
    WHERE loan_account_id = :loan_account_id::bigint AND serial_number IN (6, 7, 8) AND is_deleted = false
  )
ON CONFLICT (loan_account_id, entity_kind, entity_id) DO UPDATE SET
  due_date = EXCLUDED.due_date,
  backed_up_at = NOW();

UPDATE mfi_accounting.loan_account la
SET npa_ageing_start_date = NULL,
    npa_tagging_date = NULL,
    sec_npa_tagging_date = NULL,
    updated_on = NOW(),
    updated_by = 'QA1_MONTH_END_REG_FIXTURE'
WHERE la.account_id = :loan_account_id::bigint;

UPDATE mfi_accounting.loan_installment_details lid
SET installment_date = CASE lid.serial_number
        WHEN 6 THEN TIMESTAMP '2026-05-02 00:00:00'
        WHEN 7 THEN TIMESTAMP '2026-06-02 00:00:00'
        WHEN 8 THEN TIMESTAMP '2026-07-02 00:00:00'
      END,
    overdue_date = CASE lid.serial_number
        WHEN 6 THEN TIMESTAMP '2026-05-02 00:00:00'
        WHEN 7 THEN TIMESTAMP '2026-06-02 00:00:00'
        WHEN 8 THEN TIMESTAMP '2026-07-02 00:00:00'
      END,
    is_settled = false,
    updated_on = NOW(),
    updated_by = 'QA1_MONTH_END_REG_FIXTURE'
WHERE lid.loan_account_id = :loan_account_id::bigint
  AND lid.is_deleted = false
  AND lid.serial_number IN (6, 7, 8);

UPDATE mfi_accounting.loan_due_details ldd
SET due_date = lid.installment_date,
    overdue_date = lid.installment_date,
    paid_amount = 0,
    waived_amount = 0,
    updated_on = NOW(),
    updated_by = 'QA1_MONTH_END_REG_FIXTURE'
FROM mfi_accounting.loan_installment_details lid
WHERE ldd.loan_account_id = :loan_account_id::bigint
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND lid.id = ldd.loan_installment_details_id
  AND lid.loan_account_id = :loan_account_id::bigint
  AND lid.serial_number IN (6, 7, 8)
  AND lid.is_deleted = false;

COMMIT;

\echo '=== QA1 month-end regular fixture ==='
SELECT serial_number, installment_date::date
FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :loan_account_id::bigint AND serial_number IN (6, 7, 8) AND is_deleted = false
ORDER BY serial_number;

SELECT account_id, npa_ageing_start_date
FROM mfi_accounting.loan_account
WHERE account_id = :loan_account_id::bigint;
