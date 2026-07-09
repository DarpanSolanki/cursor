-- SDCP-11012 — QA1 audit: SHG parent DPI accrued vs sum(children).
-- Read-only. Classifies rounding (ABS(diff)<=5 both sides >0) vs structural (one side zero / large).
\set ON_ERROR_STOP on

WITH parents AS (
  SELECT account_id, la_account_number
  FROM mfi_accounting.loan_account
  WHERE has_child_accounts = true
    AND parent_loan_account_id IS NULL
    AND loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
    AND COALESCE(is_deleted, false) = false
),
parent_dpi AS (
  SELECT p.account_id, p.la_account_number,
         COALESCE(SUM(d.total_accrued_amount), 0) AS parent_accrued
  FROM parents p
  LEFT JOIN mfi_accounting.dpi_accrual_details d
    ON d.loan_account_id = p.account_id
   AND d.is_deleted = false
   AND d.total_accrued_amount > 0
  GROUP BY p.account_id, p.la_account_number
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
mm AS (
  SELECT pd.account_id,
         pd.la_account_number,
         pd.parent_accrued,
         cd.children_accrued,
         (pd.parent_accrued - cd.children_accrued) AS diff,
         CASE
           WHEN pd.parent_accrued > 0 AND cd.children_accrued > 0
                AND ABS(pd.parent_accrued - cd.children_accrued) <= 5
             THEN 'ROUNDING'
           WHEN pd.parent_accrued = 0 OR cd.children_accrued = 0
             THEN 'ONE_SIDE_ZERO'
           ELSE 'STRUCTURAL'
         END AS class
  FROM parent_dpi pd
  JOIN child_dpi cd ON cd.account_id = pd.account_id
  WHERE pd.parent_accrued <> cd.children_accrued
    AND (pd.parent_accrued > 0 OR cd.children_accrued > 0)
)
SELECT class,
       COUNT(*) AS parents,
       SUM(ABS(diff)) AS total_abs_diff
FROM mm
GROUP BY class
ORDER BY class;

-- Detail (repair candidates first)
WITH parents AS (
  SELECT account_id, la_account_number
  FROM mfi_accounting.loan_account
  WHERE has_child_accounts = true
    AND parent_loan_account_id IS NULL
    AND loan_status IN ('ACTIVE', 'FORECLOSURE_FREEZE')
    AND COALESCE(is_deleted, false) = false
),
parent_dpi AS (
  SELECT p.account_id, p.la_account_number,
         COALESCE(SUM(d.total_accrued_amount), 0) AS parent_accrued
  FROM parents p
  LEFT JOIN mfi_accounting.dpi_accrual_details d
    ON d.loan_account_id = p.account_id
   AND d.is_deleted = false
   AND d.total_accrued_amount > 0
  GROUP BY p.account_id, p.la_account_number
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
)
SELECT pd.account_id,
       pd.la_account_number,
       pd.parent_accrued,
       cd.children_accrued,
       (pd.parent_accrued - cd.children_accrued) AS diff,
       CASE
         WHEN pd.parent_accrued > 0 AND cd.children_accrued > 0
              AND ABS(pd.parent_accrued - cd.children_accrued) <= 5
           THEN 'ROUNDING'
         WHEN pd.parent_accrued = 0 OR cd.children_accrued = 0
           THEN 'ONE_SIDE_ZERO'
         ELSE 'STRUCTURAL'
       END AS class
FROM parent_dpi pd
JOIN child_dpi cd ON cd.account_id = pd.account_id
WHERE pd.parent_accrued <> cd.children_accrued
  AND (pd.parent_accrued > 0 OR cd.children_accrued > 0)
ORDER BY
  CASE
    WHEN pd.parent_accrued > 0 AND cd.children_accrued > 0
         AND ABS(pd.parent_accrued - cd.children_accrued) <= 5 THEN 0
    WHEN pd.parent_accrued = 0 OR cd.children_accrued = 0 THEN 1
    ELSE 2
  END,
  ABS(pd.parent_accrued - cd.children_accrued) DESC,
  pd.account_id;
