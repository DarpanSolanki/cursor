WITH parent AS (
  SELECT p.account_id
  FROM mfi_accounting.loan_account p
  JOIN mfi_accounting.account a ON a.id = p.account_id
  WHERE a.account_number = :'PARENT_LAN' AND p.is_deleted = false
), kids AS (
  SELECT c.account_id
  FROM mfi_accounting.loan_account c
  JOIN parent ON c.parent_loan_account_id = parent.account_id
), kdue AS (
  SELECT ldd.id, ldd.loan_account_id, ldd.component_type, ldd.due_date,
         ldd.due_amount, ldd.paid_amount, ldd.waived_amount
  FROM mfi_accounting.loan_due_details ldd
  JOIN kids k ON k.account_id = ldd.loan_account_id
  WHERE ldd.is_deleted = false
), aud AS (
  SELECT w.loan_due_details_id AS ldd_id,
         SUM(w.waived_amount) AS audit_sum,
         COUNT(*) AS audit_rows,
         MIN(w.identifier_value) AS parent_waiver_id
  FROM mfi_accounting.waiver__loan_due_details w
  JOIN kdue ON kdue.id = w.loan_due_details_id
  GROUP BY 1
), pdue AS (
  SELECT ldd.id
  FROM mfi_accounting.loan_due_details ldd
  JOIN parent ON parent.account_id = ldd.loan_account_id
  WHERE ldd.is_deleted = false
), paud AS (
  SELECT w.identifier_value, SUM(w.waived_amount) AS parent_waived
  FROM mfi_accounting.waiver__loan_due_details w
  JOIN pdue ON pdue.id = w.loan_due_details_id
  WHERE w.identifier_type = 'WAIVER'
  GROUP BY 1
), caud AS (
  SELECT w.identifier_value, SUM(w.waived_amount) AS child_waived
  FROM mfi_accounting.waiver__loan_due_details w
  JOIN kdue ON kdue.id = w.loan_due_details_id
  WHERE w.identifier_type = 'WAIVER'
  GROUP BY 1
)
SELECT COALESCE(
  (SELECT 'WAIVER_AUDIT_NOT_APPLIED_TO_DUE:ldd=' || kdue.id
          || ' child_loan_account_id=' || kdue.loan_account_id
          || ' ' || kdue.component_type
          || ' audit_rows=' || aud.audit_rows
          || ' audit_sum=' || aud.audit_sum
          || ' ldd_waived_amount=' || kdue.waived_amount
   FROM aud JOIN kdue ON kdue.id = aud.ldd_id
   WHERE kdue.waived_amount <> aud.audit_sum
   ORDER BY kdue.id LIMIT 1),
  (SELECT 'CHILD_WAIVER_SPLIT_NOT_EQUAL_PARENT:parent_waiver_id=' || paud.identifier_value
          || ' parent_waived=' || paud.parent_waived
          || ' child_sum=' || COALESCE(caud.child_waived, 0)
   FROM paud LEFT JOIN caud ON caud.identifier_value = paud.identifier_value
   WHERE COALESCE(caud.child_waived, -1) <> paud.parent_waived
   ORDER BY paud.identifier_value LIMIT 1),
  (SELECT 'WAIVED_PLUS_PAID_EXCEEDS_DUE:ldd=' || kdue.id
          || ' due_amount=' || kdue.due_amount
          || ' paid_amount=' || kdue.paid_amount
          || ' waived_amount=' || kdue.waived_amount
   FROM kdue JOIN aud ON aud.ldd_id = kdue.id
   WHERE kdue.paid_amount + kdue.waived_amount > kdue.due_amount
   ORDER BY kdue.id LIMIT 1),
  CASE
    WHEN (SELECT COUNT(*) FROM kids) = 0 THEN 'NO_CHILDREN_FOR_PARENT'
    WHEN (SELECT COUNT(*) FROM paud) = 0 THEN 'NO_PARENT_WAIVER_AUDIT_ROWS'
    WHEN (SELECT COUNT(*) FROM aud) = 0 THEN 'NO_CHILD_WAIVER_AUDIT_ROWS'
    ELSE 'SUCCESS'
  END);
