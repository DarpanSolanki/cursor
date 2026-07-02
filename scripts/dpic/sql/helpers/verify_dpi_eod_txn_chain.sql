-- DPI EOD GL chain: accrual/billing posting dates must have matching transaction_master,
-- correct catalogue (1327/1328 accrual, 1329/1330 billing), and partition rows on billing txns.
\set ON_ERROR_STOP on

WITH loan AS (
  SELECT la.account_id,
         (la.npa_ageing_start_date IS NOT NULL
          AND la.npa_ageing_start_date < COALESCE(:'as_of_date'::date, CURRENT_DATE)) AS is_npa
  FROM mfi_accounting.loan_account la
  WHERE la.account_id = :loan_account_id::bigint
),
expect AS (
  SELECT CASE WHEN is_npa THEN 1328 ELSE 1327 END AS accrual_cat,
         CASE WHEN is_npa THEN 1329 ELSE 1330 END AS billing_cat
  FROM loan
),
accrual_rows AS (
  SELECT d.id, d.end_date::date AS end_d, d.accrual_transaction_ref_number AS ref
  FROM mfi_accounting.dpi_accrual_details d
  WHERE d.loan_account_id = :loan_account_id::bigint
    AND d.is_deleted = false
    AND d.accrual_posting_date IS NOT NULL
    AND d.total_accrued_amount > 0
),
billing_rows AS (
  SELECT d.id, d.end_date::date AS end_d, d.billing_transaction_ref_number AS ref
  FROM mfi_accounting.dpi_accrual_details d
  WHERE d.loan_account_id = :loan_account_id::bigint
    AND d.is_deleted = false
    AND d.billing_posting_date IS NOT NULL
    AND d.total_accrued_amount > 0
),
accrual_orphans AS (
  SELECT COUNT(*) AS cnt
  FROM accrual_rows ar
  WHERE ar.ref IS NULL
     OR NOT EXISTS (
       SELECT 1 FROM mfi_accounting.transaction_master tm
       WHERE tm.reference_number = ar.ref
     )
),
accrual_wrong_cat AS (
  SELECT COUNT(*) AS cnt
  FROM accrual_rows ar
  CROSS JOIN expect e
  WHERE ar.ref IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM mfi_accounting.transaction_master tm
      WHERE tm.reference_number = ar.ref
        AND tm.transaction_catalogue_id <> e.accrual_cat
    )
),
billing_orphans AS (
  SELECT COUNT(*) AS cnt
  FROM billing_rows br
  WHERE br.ref IS NULL
     OR NOT EXISTS (
       SELECT 1 FROM mfi_accounting.transaction_master tm
       WHERE tm.reference_number = br.ref
     )
),
billing_wrong_cat AS (
  SELECT COUNT(*) AS cnt
  FROM billing_rows br
  CROSS JOIN expect e
  WHERE br.ref IS NOT NULL
    AND EXISTS (
      SELECT 1 FROM mfi_accounting.transaction_master tm
      WHERE tm.reference_number = br.ref
        AND tm.transaction_catalogue_id <> e.billing_cat
    )
),
billing_no_partition AS (
  SELECT COUNT(*) AS cnt
  FROM billing_rows br
  JOIN mfi_accounting.transaction_master tm ON tm.reference_number = br.ref
  WHERE NOT EXISTS (
    SELECT 1 FROM mfi_accounting.transaction_partition_details tpd
    WHERE tpd.transaction_id = tm.id
  )
),
slice_booked AS (
  SELECT COUNT(*) AS cnt
  FROM mfi_accounting.dpi_accrual_details d
  WHERE d.loan_account_id = :loan_account_id::bigint
    AND d.is_deleted = false
    AND d.end_date::date = COALESCE(NULLIF(:'slice_end_date'::text, '')::date, '1900-01-01'::date)
    AND d.accrual_posting_date IS NOT NULL
    AND d.total_accrued_amount > 0
)
SELECT e.accrual_cat,
       e.billing_cat,
       (SELECT cnt FROM accrual_orphans) AS accrual_orphans,
       (SELECT cnt FROM accrual_wrong_cat) AS accrual_wrong_catalogue,
       (SELECT cnt FROM billing_orphans) AS billing_orphans,
       (SELECT cnt FROM billing_wrong_cat) AS billing_wrong_catalogue,
       (SELECT cnt FROM billing_no_partition) AS billing_missing_partition,
       CASE
         WHEN COALESCE(NULLIF(:'slice_end_date'::text, ''), '') = '' THEN -1
         ELSE (SELECT cnt FROM slice_booked)
       END AS slice_booked_count
FROM expect e;
