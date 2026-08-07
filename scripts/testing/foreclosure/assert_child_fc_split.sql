WITH parent AS (
  SELECT p.account_id
  FROM mfi_accounting.loan_account p
  JOIN mfi_accounting.account a ON a.id = p.account_id
  WHERE a.account_number = :'PARENT_LAN' AND p.is_deleted = false
), kids AS (
  SELECT c.account_id
  FROM mfi_accounting.loan_account c
  JOIN parent ON c.parent_loan_account_id = parent.account_id
  WHERE c.is_deleted = false
), cpd AS (
  SELECT pd.*
  FROM mfi_accounting.prepayment_details pd
  JOIN kids k ON k.account_id = pd.loan_account_id
  WHERE pd.is_deleted = false AND pd.prepayment_status = 'APPROVED'
), comp AS (
  SELECT id, loan_account_id, 'balance_principal' AS c, balance_principal_amount AS amt,
         balance_principal_amount_to_be_paid AS atbp, balance_principal_waived_amount AS wv,
         balance_principal_is_fully_waived AS fw FROM cpd
  UNION ALL SELECT id, loan_account_id, 'billed_interest', billed_interest_amount,
         billed_interest_amount_to_be_paid, billed_interest_waived_amount,
         billed_interest_is_fully_waived FROM cpd
  UNION ALL SELECT id, loan_account_id, 'billed_principal', billed_principal_amount,
         billed_principal_amount_to_be_paid, billed_principal_waived_amount,
         billed_principal_is_fully_waived FROM cpd
  UNION ALL SELECT id, loan_account_id, 'billed_dpi', billed_dpi_amount,
         billed_dpi_amount_to_be_paid, billed_dpi_waived_amount,
         billed_dpi_is_fully_waived FROM cpd
  UNION ALL SELECT id, loan_account_id, 'bpi', bpi_amount,
         bpi_amount_to_be_paid, bpi_waived_amount, bpi_is_fully_waived FROM cpd
), live AS (
  SELECT * FROM comp WHERE amt IS NOT NULL AND atbp IS NOT NULL AND wv IS NOT NULL
), bad AS (
  SELECT id, c, amt, atbp, wv, fw,
    CASE
      WHEN atbp + wv <> amt THEN 'SPLIT_NOT_CONSERVED'
      WHEN COALESCE(fw, false) AND atbp <> 0 THEN 'FULLY_WAIVED_STILL_BILLED'
      WHEN COALESCE(fw, false) AND wv <> amt THEN 'FULLY_WAIVED_AMOUNT_SHORT'
      WHEN wv < 0 OR atbp < 0 THEN 'NEGATIVE_COMPONENT'
    END AS kind
  FROM live
)
SELECT COALESCE(
  (SELECT kind || ':pd=' || id || ' ' || c
          || ' amount=' || amt || ' to_be_paid=' || atbp || ' waived=' || wv
          || ' fully_waived=' || COALESCE(fw::text, 'null')
   FROM bad WHERE kind IS NOT NULL ORDER BY id, c LIMIT 1),
  CASE
    WHEN (SELECT COUNT(*) FROM kids) = 0 THEN 'NO_CHILDREN_FOR_PARENT'
    WHEN (SELECT COUNT(DISTINCT loan_account_id) FROM cpd) < (SELECT COUNT(*) FROM kids)
      THEN 'CHILD_PREPAYMENT_MISSING:' || (SELECT COUNT(DISTINCT loan_account_id) FROM cpd)
           || '/' || (SELECT COUNT(*) FROM kids)
    WHEN (SELECT COUNT(*) FROM live) = 0 THEN 'NO_CHILD_PREPAYMENT_COMPONENTS'
    ELSE 'SUCCESS'
  END);
