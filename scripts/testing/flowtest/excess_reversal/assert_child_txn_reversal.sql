WITH la AS (
  SELECT l.account_id FROM mfi_accounting.loan_account l
  WHERE l.la_account_number = '${CHILD_LAN}' AND l.is_deleted = false
), base_due AS (
  SELECT * FROM (VALUES ${DUES_BASELINE}) AS t(due_id, paid_amount, waived_amount)
), base_inst AS (
  SELECT * FROM (VALUES ${INST_BASELINE}) AS t(inst_id, settled_amount)
), q AS (
  SELECT event_status, filler_1 FROM mfi_accounting.loan_account_events_queue WHERE id = ${QUEUE_ID}
), orig AS (
  SELECT principal_amount, interest_amount, penalty_amount, fee_amount, excess_amount, amount, dpi_amount,
         transaction_reference_number
  FROM mfi_accounting.loan_account_payments_details WHERE id = ${ORIG_LAPD_ID}
), rev AS (
  SELECT pd.id, pd.principal_amount, pd.interest_amount, pd.penalty_amount, pd.fee_amount,
         pd.excess_amount, pd.amount, pd.dpi_amount
  FROM mfi_accounting.loan_account_payments_details pd
  JOIN la ON la.account_id = pd.loan_account_id
  WHERE pd.transaction_reference_number = 'R_' || (SELECT transaction_reference_number FROM orig)
), due_drift AS (
  SELECT b.due_id,
         (d.paid_amount - b.paid_amount)::numeric(18,6)   AS paid_delta,
         (d.waived_amount - b.waived_amount)::numeric(18,6) AS waived_delta
  FROM base_due b
  JOIN mfi_accounting.loan_due_details d ON d.id = b.due_id
), inst_drift AS (
  SELECT b.inst_id, (i.settled_amount - b.settled_amount)::numeric(18,6) AS settled_delta
  FROM base_inst b
  JOIN mfi_accounting.loan_installment_details i ON i.id = b.inst_id
)
SELECT CASE
  WHEN (SELECT COUNT(*) FROM la) <> 1
    THEN 'LAN_NOT_RESOLVED:${CHILD_LAN}'
  WHEN (SELECT event_status FROM q) IS DISTINCT FROM 'C'
    THEN 'QUEUE_NOT_DRAINED:' || COALESCE((SELECT event_status FROM q), 'MISSING')
  WHEN (SELECT filler_1 FROM q) IS NOT NULL
    THEN 'QUEUE_ERROR:' || LEFT((SELECT filler_1 FROM q), 120)
  WHEN (SELECT COUNT(*) FROM rev) <> 1
    THEN 'OFFSETTING_PAYMENT_ROWS:' || (SELECT COUNT(*) FROM rev)::text
  WHEN (SELECT COUNT(*) FROM due_drift WHERE paid_delta <> 0) > 0
    THEN 'DUE_PAID_NOT_RESTORED:' || (SELECT string_agg(due_id::text || '=' || paid_delta::text, ',' ORDER BY due_id) FROM due_drift WHERE paid_delta <> 0)
  WHEN (SELECT COUNT(*) FROM due_drift WHERE waived_delta <> 0) > 0
    THEN 'DUE_WAIVED_NOT_RESTORED:' || (SELECT string_agg(due_id::text || '=' || waived_delta::text, ',' ORDER BY due_id) FROM due_drift WHERE waived_delta <> 0)
  WHEN (SELECT COUNT(*) FROM inst_drift WHERE settled_delta <> 0) > 0
    THEN 'INSTALLMENT_SETTLED_NOT_RESTORED:' || (SELECT string_agg(inst_id::text || '=' || settled_delta::text, ',' ORDER BY inst_id) FROM inst_drift WHERE settled_delta <> 0)
  WHEN (SELECT r.principal_amount FROM rev r) <> (SELECT o.principal_amount FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:principal:' || ((SELECT r.principal_amount FROM rev r) - (SELECT o.principal_amount FROM orig o))::text
  WHEN (SELECT r.interest_amount FROM rev r) <> (SELECT o.interest_amount FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:interest:' || ((SELECT r.interest_amount FROM rev r) - (SELECT o.interest_amount FROM orig o))::text
  WHEN (SELECT r.penalty_amount FROM rev r) <> (SELECT o.penalty_amount FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:penalty:' || ((SELECT r.penalty_amount FROM rev r) - (SELECT o.penalty_amount FROM orig o))::text
  WHEN (SELECT r.fee_amount FROM rev r) <> (SELECT o.fee_amount FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:fee:' || ((SELECT r.fee_amount FROM rev r) - (SELECT o.fee_amount FROM orig o))::text
  WHEN (SELECT r.excess_amount FROM rev r) <> (SELECT o.excess_amount FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:excess:' || ((SELECT r.excess_amount FROM rev r) - (SELECT o.excess_amount FROM orig o))::text
  WHEN (SELECT COALESCE(r.dpi_amount, 0) FROM rev r) <> (SELECT COALESCE(o.dpi_amount, 0) FROM orig o)
    THEN 'REVERSAL_SPLIT_MISMATCH:dpi:' || ((SELECT COALESCE(r.dpi_amount, 0) FROM rev r) - (SELECT COALESCE(o.dpi_amount, 0) FROM orig o))::text
  WHEN (SELECT r.amount FROM rev r) <> (SELECT o.amount FROM orig o)
    THEN 'REVERSAL_TOTAL_MISMATCH:' || ((SELECT r.amount FROM rev r) - (SELECT o.amount FROM orig o))::text
  WHEN (SELECT COALESCE(tm.reversed, false) FROM mfi_accounting.transaction_master tm
        WHERE tm.reference_number = (SELECT transaction_reference_number FROM orig)) IS DISTINCT FROM true
    THEN 'ORIGINAL_TXN_NOT_MARKED_REVERSED:' || (SELECT transaction_reference_number FROM orig)
  ELSE 'SUCCESS'
END;
