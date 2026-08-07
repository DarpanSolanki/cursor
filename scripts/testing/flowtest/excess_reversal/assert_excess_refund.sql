WITH la AS (
  SELECT l.account_id, COALESCE(l.excess_amount, 0)::numeric(18,6) AS excess_after
  FROM mfi_accounting.loan_account l
  WHERE l.la_account_number = '${ACCOUNT_NUMBER}' AND l.is_deleted = false
), r AS (
  SELECT MAX(d.refund_effective_date) AS eff_date,
         COALESCE(SUM(d.total_refund_amount) FILTER (WHERE d.status = 'SUCCESS' AND d.task_status = 'APPROVED'), 0)::numeric(18,6) AS declared,
         COUNT(*) FILTER (WHERE d.status = 'PENDING_FOR_APPR') AS still_pending
  FROM mfi_accounting.loan_account_excess_amount_refund_details d
  JOIN la ON la.account_id = d.loan_account_id
  WHERE d.id > ${SINCE_REFUND_ID}
), p AS (
  SELECT COALESCE(SUM(pd.excess_amount), 0)::numeric(18,6) AS moved,
         COALESCE(SUM(pd.principal_amount + pd.interest_amount + pd.penalty_amount + pd.fee_amount), 0)::numeric(18,6) AS split_leak,
         COALESCE(SUM(pd.amount - pd.excess_amount), 0)::numeric(18,6) AS amount_drift,
         COUNT(*) AS n
  FROM mfi_accounting.loan_account_payments_details pd
  JOIN la ON la.account_id = pd.loan_account_id
  WHERE pd.client_reference_number LIKE 'EAR' || la.account_id::text || '%'
    AND pd.id > ${SINCE_LAPD_ID}
), dues AS (
  SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0)::numeric(18,6) AS open_at_eff
  FROM mfi_accounting.loan_due_details ldd
  JOIN la ON la.account_id = ldd.loan_account_id
  WHERE ldd.is_deleted = false
    AND ldd.due_date::date <= (SELECT eff_date::date FROM r)
    AND ldd.due_amount > ldd.paid_amount + ldd.waived_amount
)
SELECT CASE
  WHEN (SELECT COUNT(*) FROM la) <> 1
    THEN 'LAN_NOT_RESOLVED:${ACCOUNT_NUMBER}'
  WHEN (SELECT declared FROM r) = 0
    THEN 'NO_APPROVED_REFUND_IN_WINDOW:${ACCOUNT_NUMBER}'
  WHEN (SELECT n FROM p) = 0
    THEN 'REFUND_APPROVED_WITHOUT_PAYMENT_ROW:' || (SELECT declared FROM r)::text
  WHEN (SELECT split_leak FROM p) <> 0
    THEN 'REFUND_SPLIT_LEAK:' || (SELECT split_leak FROM p)::text
  WHEN (SELECT amount_drift FROM p) <> 0
    THEN 'REFUND_AMOUNT_NE_EXCESS:' || (SELECT amount_drift FROM p)::text
  WHEN (SELECT moved FROM p) <> (SELECT declared FROM r)
    THEN 'REFUND_MOVED_NE_DECLARED:' || ((SELECT moved FROM p) - (SELECT declared FROM r))::text
  WHEN (SELECT excess_after FROM la) < 0
    THEN 'REFUNDED_MORE_THAN_HELD:' || (SELECT excess_after FROM la)::text
  WHEN (SELECT excess_after FROM la) <> (SELECT open_at_eff FROM dues)
    THEN 'EXCESS_LEFT_NE_DUES_AT_EFFECTIVE_DATE:' || ((SELECT excess_after FROM la) - (SELECT open_at_eff FROM dues))::text
  WHEN (SELECT still_pending FROM r) <> 0
    THEN 'REFUND_STILL_PENDING:' || (SELECT still_pending FROM r)::text
  ELSE 'SUCCESS'
END;
