-- Death foreclosure outstanding component reconciliation (read-only sanity).
-- Mirrors GetAmountDetailsForDeathForeclosureService high-level buckets.
-- Usage:
--   psql -h localhost -p 5433 -U yugabyte -d yugabyte -v ON_ERROR_STOP=1 \
--     -v lan='6007564726' -v death_date='2026-10-01' \
--     -f scripts/dcf_sanity/dcf_amount_reconcile.sql

\set ON_ERROR_STOP on
\set schema 'mfi_accounting'

\echo '=== Account + insurance ==='
SELECT la.account_id,
       la.account_number,
       la.excess_amount,
       lai.sum_assured
FROM :schema.loan_account la
LEFT JOIN :schema.loan_account_insurance_details lai
  ON lai.loan_account_id = la.account_id AND lai.is_deleted = false AND lai.policy_type = 'LIFE_INSUR'
WHERE la.account_number = :'lan' AND la.is_deleted = false
LIMIT 1;

\echo '=== Overdue PRIN+INT (due_date < death) ==='
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS overdue_prin_int
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.is_deleted = false
  AND ldd.component_type IN ('PRIN', 'INT')
  AND ldd.due_date < :'death_date'::date
  AND (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) > 0;

\echo '=== Future PRIN (due_date >= death) ==='
SELECT COALESCE(SUM(ldd.due_amount - ldd.paid_amount - ldd.waived_amount), 0) AS future_prin
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.component_type = 'PRIN'
  AND ldd.due_date >= :'death_date'::date
  AND ldd.is_deleted = false;

\echo '=== INT paid vs net scheduled till death-1 ==='
SELECT
  COALESCE(SUM(ldd.paid_amount), 0) AS int_paid_all,
  COALESCE(SUM(CASE WHEN ldd.due_date <= (:'death_date'::date - 1)
                    THEN ldd.due_amount - COALESCE(ldd.waived_amount, 0) ELSE 0 END), 0) AS int_net_scheduled_till_death_minus_one
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.component_type = 'INT'
  AND ldd.is_deleted = false;

\echo '=== PINT/FEE aggregate overpay till death ==='
SELECT ldd.component_type,
       COALESCE(SUM(ldd.paid_amount), 0) AS paid_all,
       COALESCE(SUM(CASE WHEN ldd.due_date <= :'death_date'::date
                         THEN ldd.due_amount - COALESCE(ldd.waived_amount, 0) ELSE 0 END), 0) AS owed_till_death,
       GREATEST(COALESCE(SUM(ldd.paid_amount), 0)
         - COALESCE(SUM(CASE WHEN ldd.due_date <= :'death_date'::date
                            THEN ldd.due_amount - COALESCE(ldd.waived_amount, 0) ELSE 0 END), 0), 0) AS aggregate_overpay
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.component_type IN ('PINT', 'FEE')
  AND ldd.is_deleted = false
GROUP BY ldd.component_type;

\echo '=== Death-cycle settled EMI (due_date = death) ==='
SELECT ldd.component_type,
       ldd.due_amount,
       ldd.paid_amount,
       ldd.waived_amount,
       (ldd.due_amount - ldd.paid_amount - ldd.waived_amount) AS pending
FROM :schema.loan_due_details ldd
JOIN :schema.loan_account la ON la.account_id = ldd.loan_account_id
WHERE la.account_number = :'lan'
  AND ldd.due_date = :'death_date'::date
  AND ldd.is_deleted = false
ORDER BY ldd.component_type;

\echo '=== Stored DCF amounts (if case exists) ==='
SELECT dfd.outstanding_loan_balance,
       dfd.balance_claim_amount,
       dfd.date_of_death::date
FROM :schema.death_foreclosure_details dfd
JOIN :schema.loan_account la ON la.account_id = dfd.loan_account_id
WHERE la.account_number = :'lan'
ORDER BY dfd.id DESC
LIMIT 1;
