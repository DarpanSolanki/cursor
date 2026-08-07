WITH ci AS (
  SELECT id, loan_account_id, serial_number, installment_amount, installment_date, overdue_date, schedule_number
    FROM mfi_accounting.loan_installment_details
   WHERE loan_account_id IN (:child_ids) AND is_deleted = false),
cd AS (
  SELECT id, loan_account_id, loan_installment_details_id, component_type, due_amount
    FROM mfi_accounting.loan_due_details
   WHERE loan_account_id IN (:child_ids) AND is_deleted = false),
pi AS (
  SELECT id, serial_number, installment_amount, installment_date, overdue_date, schedule_number
    FROM mfi_accounting.loan_installment_details
   WHERE loan_account_id = :parent_id AND is_deleted = false),
pd AS (
  SELECT loan_installment_details_id, due_amount
    FROM mfi_accounting.loan_due_details
   WHERE loan_account_id = :parent_id AND is_deleted = false AND component_type = 'PRIN')
SELECT
 (SELECT count(*) FROM (SELECT 1 FROM ci JOIN cd ON cd.loan_installment_details_id = ci.id
    GROUP BY ci.id, ci.installment_amount HAVING SUM(cd.due_amount) <> ci.installment_amount) t) AS b_due_sum_ne_emi,
 (SELECT count(*) FROM cd JOIN mfi_accounting.loan_installment_details i ON i.id = cd.loan_installment_details_id
   WHERE i.loan_account_id <> cd.loan_account_id) AS c_cross_loan_fk_rows,
 (SELECT count(*) FROM (SELECT 1 FROM pi JOIN ci ON ci.serial_number = pi.serial_number
    GROUP BY pi.id, pi.installment_amount HAVING SUM(ci.installment_amount) <> pi.installment_amount) t) AS d_emi_split_ne_parent,
 (SELECT count(*) FROM (SELECT 1 FROM pi JOIN pd ON pd.loan_installment_details_id = pi.id
    JOIN ci ON ci.serial_number = pi.serial_number
    JOIN cd ON cd.loan_installment_details_id = ci.id AND cd.component_type = 'PRIN'
    GROUP BY pi.id, pd.due_amount HAVING SUM(cd.due_amount) <> pd.due_amount) t) AS d_prin_split_ne_parent,
 (SELECT count(*) FROM pi JOIN ci ON ci.serial_number = pi.serial_number
   WHERE ci.installment_date <> pi.installment_date OR ci.overdue_date <> pi.overdue_date
      OR ci.schedule_number <> pi.schedule_number) AS e_calendar_mismatch,
 (SELECT count(*) FROM cd WHERE component_type NOT IN ('PRIN','INT')) AS f_unexpected_component,
 (SELECT count(*) FROM (SELECT loan_account_id FROM ci GROUP BY loan_account_id) t) AS children,
 (SELECT count(*) FROM ci) AS child_installments,
 (SELECT count(*) FROM pi) AS parent_installments;
