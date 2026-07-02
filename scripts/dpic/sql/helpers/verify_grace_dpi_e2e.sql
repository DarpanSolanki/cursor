-- Assert DPI grace gate on local E2E loan after dpiAccrualCalculation.
-- Fails psql (ON_ERROR_STOP) when expectations are not met.
--
-- Vars: loan_account_id, first_emi_due_date (YYYY-MM-DD), grace_days

\set ON_ERROR_STOP on

\echo '=== grace E2E verify ==='

WITH cfg AS (
  SELECT :loan_account_id::bigint AS loan_id,
         :'first_emi_due_date'::date AS first_due,
         :grace_days::int AS grace
),
gate AS (
  SELECT loan_id, first_due, first_due + (grace + 1) AS gate_end_date
  FROM cfg
),
first_accrual AS (
  SELECT d.start_date::date AS start_date,
         d.end_date::date AS end_date,
         d.total_accrued_amount
  FROM mfi_accounting.dpi_accrual_details d
  CROSS JOIN cfg
  WHERE d.loan_account_id = cfg.loan_id
    AND d.is_deleted = false
    AND d.total_accrued_amount > 0
  ORDER BY d.end_date ASC
  LIMIT 1
),
checks AS (
  SELECT
    (SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details d CROSS JOIN gate g
      WHERE d.loan_account_id = g.loan_id AND d.is_deleted = false
        AND d.total_accrued_amount > 0 AND d.end_date::date <= g.gate_end_date) AS accruals_inside_grace,
    (SELECT start_date FROM first_accrual) AS first_start,
    (SELECT end_date FROM first_accrual) AS first_end,
    (SELECT total_accrued_amount FROM first_accrual) AS first_amount,
    (SELECT first_due FROM gate) AS expected_start,
    (SELECT gate_end_date FROM gate) AS gate_end
)
SELECT * FROM checks;

DO $$
DECLARE
  v_inside_grace INT;
  v_first_start DATE;
  v_first_end DATE;
  v_first_amount NUMERIC;
  v_expected_start DATE;
  v_gate_end DATE;
BEGIN
  SELECT c.accruals_inside_grace, c.first_start, c.first_end, c.first_amount,
         c.expected_start, c.gate_end
  INTO v_inside_grace, v_first_start, v_first_end, v_first_amount,
       v_expected_start, v_gate_end
  FROM (
    WITH cfg AS (
      SELECT :loan_account_id::bigint AS loan_id,
             :'first_emi_due_date'::date AS first_due,
             :grace_days::int AS grace
    ),
    gate AS (
      SELECT loan_id, first_due, first_due + (grace + 1) AS gate_end_date FROM cfg
    ),
    first_accrual AS (
      SELECT d.start_date::date AS start_date, d.end_date::date AS end_date, d.total_accrued_amount
      FROM mfi_accounting.dpi_accrual_details d CROSS JOIN cfg
      WHERE d.loan_account_id = cfg.loan_id AND d.is_deleted = false AND d.total_accrued_amount > 0
      ORDER BY d.end_date ASC LIMIT 1
    )
    SELECT
      (SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details d CROSS JOIN gate g
        WHERE d.loan_account_id = g.loan_id AND d.is_deleted = false
          AND d.total_accrued_amount > 0 AND d.end_date::date <= g.gate_end_date),
      (SELECT start_date FROM first_accrual),
      (SELECT end_date FROM first_accrual),
      (SELECT total_accrued_amount FROM first_accrual),
      (SELECT first_due FROM gate),
      (SELECT gate_end_date FROM gate)
  ) c;

  IF v_first_start IS NULL THEN
    RAISE EXCEPTION 'grace E2E FAIL: no dpi_accrual_details row with amount > 0';
  END IF;

  IF v_inside_grace > 0 THEN
    RAISE EXCEPTION 'grace E2E FAIL: % accrual row(s) with end_date <= gate %', v_inside_grace, v_gate_end;
  END IF;

  IF v_first_start <> v_expected_start THEN
    RAISE EXCEPTION 'grace E2E FAIL: first start_date % <> EMI due %', v_first_start, v_expected_start;
  END IF;

  IF v_first_end <= v_gate_end THEN
    RAISE EXCEPTION 'grace E2E FAIL: first end_date % not after gate %', v_first_end, v_gate_end;
  END IF;

  RAISE NOTICE 'grace E2E PASS: gate_end=% first=[%..%] amount=% start=due_date=%',
    v_gate_end, v_first_start, v_first_end, v_first_amount, v_expected_start;
END $$;
