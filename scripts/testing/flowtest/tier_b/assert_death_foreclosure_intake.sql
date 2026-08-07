WITH d AS (
  SELECT dfd.id, dfd.loan_account_id, dfd.death_foreclosure_status, dfd.outstanding_loan_balance,
         dfd.balance_claim_amount, dfd.excess_amount, dfd.approved_on,
         la.loan_status, la.excess_amount AS la_excess
    FROM mfi_accounting.death_foreclosure_details dfd
    JOIN mfi_accounting.loan_account la ON la.account_id = dfd.loan_account_id
   WHERE dfd.id IN (:dfc_ids)),
s AS (
  SELECT death_foreclosure_details_id AS dfc_id, outstanding_loan_balance, balance_claim_amount,
         sum_assured, claim_status
    FROM mfi_accounting.death_foreclosure_insurance_staging_details
   WHERE death_foreclosure_details_id IN (:dfc_ids) AND is_deleted = false)
SELECT
 (SELECT count(*) FROM d JOIN s ON s.dfc_id = d.id
   WHERE s.outstanding_loan_balance <> d.outstanding_loan_balance)              AS a_outstanding_stage_mismatch,
 (SELECT count(*) FROM d JOIN s ON s.dfc_id = d.id
   WHERE s.balance_claim_amount <> d.balance_claim_amount)                      AS b_claim_stage_mismatch,
 (SELECT count(*) FROM d JOIN s ON s.dfc_id = d.id
   WHERE d.balance_claim_amount <> GREATEST(s.sum_assured - d.outstanding_loan_balance, 0)) AS c_claim_formula_broken,
 (SELECT count(*) FROM d WHERE d.outstanding_loan_balance IS NULL
      OR d.balance_claim_amount IS NULL)                                        AS d_amount_null,
 (SELECT count(*) FROM d WHERE d.death_foreclosure_status NOT IN
      ('INITIATED_DEATH_FORECLOSURE','PENDING','APPROVED','REJECTED','RE_UPLOAD_DOCUMENT')) AS e_status_illegal,
 (SELECT count(*) FROM d WHERE d.death_foreclosure_status = 'APPROVED'
      AND d.loan_status NOT IN ('DEATH_FORECLOSURE_FREEZE','CLOSED'))           AS f_loan_status_illegal,
 (SELECT count(*) FROM d)                                                       AS rows_checked;
