-- ============================================================================
-- Interest Accrual Calculation Query Performance Test
-- ============================================================================
-- Replace the following variables with actual values:
--   - :minValue (e.g., 171033)
--   - :maxValue (e.g., 5427802)
--   - :businessDate (e.g., '2025-10-17')
-- ============================================================================

-- ============================================================================
-- OLD QUERY (Original - LEFT JOIN Pattern)
-- ============================================================================
-- Expected execution time: ~5 seconds (up to 250 seconds in worst cases)
-- ============================================================================

EXPLAIN ANALYZE
SELECT 
    la.account_id,
    a.currency,
    la.expected_disbursement_date,
    acs.stop_interest_accrual,
    la.asset_classification_slabs_id,
    lp.product_id,
    a.account_number,
    a.office_id,
    la.interest_calculation_basis,
    la.approved_amount,
    la.interest_frequency,
    ps.interest_calculation_days_in_month,
    ps.interest_calculation_days_in_year,
    la.maturity_date,
    la.first_repayment_date,
    lp.interest_rounding_factor
FROM loan_account la
JOIN account a ON a.id = la.account_id
JOIN loan_product lp ON la.loan_product_id = lp.id
JOIN product_scheme ps ON a.product_scheme_id = ps.id
JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id
JOIN asset_criteria_slabs acs ON acs.id = la.asset_classification_slabs_id
    AND lpac.asset_criteria_slab_id = la.asset_classification_slabs_id
LEFT JOIN batch_failure_audit bfa ON 
    la.account_id = bfa.context_value::int4
    AND group_code = 'LMS-EOD-BOD'
    AND ((sub_group_code = 'LMS-BOD' 
          AND business_date = DATE('2025-10-17'))
         OR (sub_group_code = 'LMS-EOD' 
             AND business_date = DATE('2025-10-17') - 1))
WHERE (la.loan_status = 'ACTIVE')
    AND la.account_id >= 171033 
    AND la.account_id <= 5427802
    AND bfa.context_value IS NULL;

-- ============================================================================
-- NEW QUERY (Optimized - CTE with NOT IN Pattern)
-- ============================================================================
-- Expected execution time: ~250ms (20x to 1000x faster)
-- ============================================================================

EXPLAIN ANALYZE
WITH filtered_loan_accounts AS (
    SELECT la.* 
    FROM loan_account la
    WHERE la.loan_status = 'ACTIVE'
      AND la.account_id >= 171033
      AND la.account_id <= 5427802
      AND la.account_id NOT IN (
          SELECT (context_value::int4) 
          FROM batch_failure_audit
          WHERE group_code = 'LMS-EOD-BOD' 
            AND sub_group_code = 'LMS-BOD'
            AND business_date = DATE('2025-10-17')
            AND context_value IS NOT NULL
      )
      AND la.account_id NOT IN (
          SELECT (context_value::int4) 
          FROM batch_failure_audit
          WHERE group_code = 'LMS-EOD-BOD'
            AND sub_group_code = 'LMS-EOD'
            AND business_date = DATE('2025-10-17') - 1
            AND context_value IS NOT NULL
      )
), 
la_with_account AS (
    SELECT la.*, 
           a.product_scheme_id, 
           a.currency, 
           a.account_number, 
           a.office_id
    FROM filtered_loan_accounts la
    INNER JOIN account a ON a.id = la.account_id
)
SELECT 
    la.account_id,
    la.currency,
    la.expected_disbursement_date,
    acs.stop_interest_accrual,
    la.asset_classification_slabs_id,
    lp.product_id,
    la.account_number,
    la.office_id,
    la.interest_calculation_basis,
    la.approved_amount,
    la.interest_frequency,
    ps.interest_calculation_days_in_month,
    ps.interest_calculation_days_in_year,
    la.maturity_date,
    la.first_repayment_date,
    lp.interest_rounding_factor
FROM la_with_account la
INNER JOIN product_scheme ps ON ps.id = la.product_scheme_id
INNER JOIN loan_product lp ON la.loan_product_id = lp.id
INNER JOIN loan_product_asset_criteria lpac 
    ON lpac.product_id = lp.product_id 
    AND lpac.asset_criteria_slab_id = la.asset_classification_slabs_id
INNER JOIN asset_criteria_slabs acs ON acs.id = la.asset_classification_slabs_id;

-- ============================================================================
-- PERFORMANCE COMPARISON QUERIES (Without EXPLAIN ANALYZE)
-- ============================================================================
-- Use these to get actual row counts and verify results are identical
-- ============================================================================

-- OLD QUERY - Count rows
SELECT COUNT(*) as old_query_count
FROM loan_account la
JOIN account a ON a.id = la.account_id
JOIN loan_product lp ON la.loan_product_id = lp.id
JOIN product_scheme ps ON a.product_scheme_id = ps.id
JOIN loan_product_asset_criteria lpac ON lpac.product_id = lp.product_id
JOIN asset_criteria_slabs acs ON acs.id = la.asset_classification_slabs_id
    AND lpac.asset_criteria_slab_id = la.asset_classification_slabs_id
LEFT JOIN batch_failure_audit bfa ON 
    la.account_id = bfa.context_value::int4
    AND group_code = 'LMS-EOD-BOD'
    AND ((sub_group_code = 'LMS-BOD' 
          AND business_date = DATE('2025-10-17'))
         OR (sub_group_code = 'LMS-EOD' 
             AND business_date = DATE('2025-10-17') - 1))
WHERE (la.loan_status = 'ACTIVE')
    AND la.account_id >= 171033 
    AND la.account_id <= 5427802
    AND bfa.context_value IS NULL;

-- NEW QUERY - Count rows
WITH filtered_loan_accounts AS (
    SELECT la.* 
    FROM loan_account la
    WHERE la.loan_status = 'ACTIVE'
      AND la.account_id >= 171033
      AND la.account_id <= 5427802
      AND la.account_id NOT IN (
          SELECT (context_value::int4) 
          FROM batch_failure_audit
          WHERE group_code = 'LMS-EOD-BOD' 
            AND sub_group_code = 'LMS-BOD'
            AND business_date = DATE('2025-10-17')
            AND context_value IS NOT NULL
      )
      AND la.account_id NOT IN (
          SELECT (context_value::int4) 
          FROM batch_failure_audit
          WHERE group_code = 'LMS-EOD-BOD'
            AND sub_group_code = 'LMS-EOD'
            AND business_date = DATE('2025-10-17') - 1
            AND context_value IS NOT NULL
      )
), 
la_with_account AS (
    SELECT la.*, 
           a.product_scheme_id, 
           a.currency, 
           a.account_number, 
           a.office_id
    FROM filtered_loan_accounts la
    INNER JOIN account a ON a.id = la.account_id
)
SELECT COUNT(*) as new_query_count
FROM la_with_account la
INNER JOIN product_scheme ps ON ps.id = la.product_scheme_id
INNER JOIN loan_product lp ON la.loan_product_id = lp.id
INNER JOIN loan_product_asset_criteria lpac 
    ON lpac.product_id = lp.product_id 
    AND lpac.asset_criteria_slab_id = la.asset_classification_slabs_id
INNER JOIN asset_criteria_slabs acs ON acs.id = la.asset_classification_slabs_id;

-- ============================================================================
-- NOTES:
-- ============================================================================
-- 1. Replace '2025-10-17' with your actual business date
-- 2. Replace 171033 and 5427802 with your actual min/max account_id values
-- 3. Run EXPLAIN ANALYZE on both queries to compare execution plans and times
-- 4. Verify both queries return the same row count
-- 5. The new query should show:
--    - Hash Anti-Join instead of Nested Loop Anti-Join
--    - Index scans instead of sequential scans
--    - Significantly lower execution time
-- ============================================================================

-- ============================================================================
-- INSURANCE CALCULATION MATRIX SLAB DETAILS - SIMPLE CHECK QUERIES
-- ============================================================================

-- Simple query to check data format (no casting)
SELECT 
    icmsd.id,
    icmsd.age_slab,
    icmsd.amount_slab,
    icmsd.term_slab,
    icmsd.gender,
    icmsd.term_unit
FROM insurance_calculation_matrix_slab_details icmsd
WHERE icmsd.premium_calculation_id = (
    SELECT pcd.id 
    FROM premium_calculation_details pcd
    INNER JOIN insurance_product ip ON ip.premium_calculation_code = pcd.code
    INNER JOIN product p ON p.id = ip.product_id
    WHERE p.code = 'SHGDL'  -- Replace with your product code
      AND ip.is_deleted = false
)
  AND icmsd.gender = 'FEMALE'        -- Replace (e.g., 'MALE')
  AND icmsd.term_unit = '30'         -- Replace (e.g., 'MONTH')
  AND icmsd.is_deleted = false;

-- Query with age range check (PostgreSQL compatible - using INTEGER instead of UNSIGNED)
SELECT 
    icmsd.id,
    icmsd.age_slab,
    icmsd.amount_slab,
    icmsd.term_slab,
    CASE 
        WHEN CAST(SUBSTRING(icmsd.age_slab FROM '^[0-9]+') AS INTEGER) < 68
             AND CAST(SUBSTRING(icmsd.age_slab FROM '[0-9]+$') AS INTEGER) >= 17
        THEN 'MATCHES' 
        ELSE 'NO MATCH' 
    END as age_69_status
FROM insurance_calculation_matrix_slab_details icmsd
WHERE icmsd.premium_calculation_id = (
    SELECT pcd.id 
    FROM premium_calculation_details pcd
    INNER JOIN insurance_product ip ON ip.premium_calculation_code = pcd.code
    INNER JOIN product p ON p.id = ip.product_id
    WHERE p.code = 'SHGDL'  -- Replace with your product code
      AND ip.is_deleted = false
)
  AND icmsd.gender = 'FEMALE'        -- Replace (e.g., 'MALE')
  AND icmsd.term_unit = '30'         -- Replace (e.g., 'MONTH')
  AND icmsd.is_deleted = false;

-- Alternative query using SPLIT_PART (if age_slab format is "17TO68")
SELECT 
    icmsd.id,
    icmsd.age_slab,
    icmsd.amount_slab,
    icmsd.term_slab,
    SPLIT_PART(icmsd.age_slab, 'TO', 1) as min_age,
    SPLIT_PART(icmsd.age_slab, 'TO', 2) as max_age,
    CASE 
        WHEN CAST(SPLIT_PART(icmsd.age_slab, 'TO', 1) AS INTEGER) < 68
             AND CAST(SPLIT_PART(icmsd.age_slab, 'TO', 2) AS INTEGER) >= 17
        THEN 'MATCHES' 
        ELSE 'NO MATCH' 
    END as age_69_status
FROM insurance_calculation_matrix_slab_details icmsd
WHERE icmsd.premium_calculation_id = (
    SELECT pcd.id 
    FROM premium_calculation_details pcd
    INNER JOIN insurance_product ip ON ip.premium_calculation_code = pcd.code
    INNER JOIN product p ON p.id = ip.product_id
    WHERE p.code = 'SHGDL'  -- Replace with your product code
      AND ip.is_deleted = false
)
  AND icmsd.gender = 'FEMALE'        -- Replace (e.g., 'MALE')
  AND icmsd.term_unit = '30'         -- Replace (e.g., 'MONTH')
  AND icmsd.is_deleted = false;

-- ============================================================================
-- INSURANCE AVAILABILITY CHECK - With Age, Tenure, and Amount Input
-- ============================================================================
-- This query checks if insurance is available for given age, tenure (in months), and amount
-- Replace the following values in the query:
--   - Age: Replace 25 with the actual age
--   - Tenure: Replace 36 with the actual tenure in months
--   - Amount: Replace 100000.00 with the actual loan amount
--   - Product Code: Replace 'INSPro841837' with your product code
--   - Gender: Replace 'MALE' with 'MALE' or 'FEMALE'
-- 
-- Logic: value > min && value <= max (matches Java code logic)
-- ============================================================================

-- Simple YES/NO query to check if insurance is available
SELECT 
    CASE 
        WHEN COUNT(*) > 0 THEN 'YES - Insurance Available'
        ELSE 'NO - Insurance Not Available'
    END as insurance_available,
    COUNT(*) as matching_slabs_count
FROM insurance_calculation_matrix_slab_details icmsd
WHERE icmsd.premium_calculation_id = (
    SELECT pcd.id 
    FROM premium_calculation_details pcd
    INNER JOIN insurance_product ip ON ip.premium_calculation_code = pcd.code
    INNER JOIN product p ON p.id = ip.product_id
    WHERE p.code = 'INSPro841837'  -- Replace with your product code
      AND ip.is_deleted = false
)
  AND icmsd.gender = 'MALE'         -- Replace with input gender (e.g., 'MALE', 'FEMALE')
  AND icmsd.term_unit = 'MONTH'     -- Assuming term_unit is 'MONTH' for tenure in months
  AND icmsd.is_deleted = false
  -- Check if age falls within age_slab range (value > min && value <= max)
  AND 25 > CAST(SPLIT_PART(icmsd.age_slab, 'TO', 1) AS INTEGER)  -- Replace 25 with input age
  AND 25 <= CAST(SPLIT_PART(icmsd.age_slab, 'TO', 2) AS INTEGER)  -- Replace 25 with input age
  -- Check if tenure falls within term_slab range (value > min && value <= max)
  AND 36 > CAST(SPLIT_PART(icmsd.term_slab, 'TO', 1) AS INTEGER)  -- Replace 36 with input tenure in months
  AND 36 <= CAST(SPLIT_PART(icmsd.term_slab, 'TO', 2) AS INTEGER)  -- Replace 36 with input tenure in months
  -- Check if amount falls within amount_slab range (amount > min && amount <= max)
  AND 100000.00 > CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 1) AS DECIMAL)  -- Replace 100000.00 with input amount
  AND 100000.00 <= CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 2) AS DECIMAL); -- Replace 100000.00 with input amount

-- Alternative: Detailed query showing all matching slabs with details
SELECT 
    icmsd.id,
    icmsd.age_slab,
    icmsd.term_slab,
    icmsd.amount_slab,
    CAST(SPLIT_PART(icmsd.age_slab, 'TO', 1) AS INTEGER) as age_min,
    CAST(SPLIT_PART(icmsd.age_slab, 'TO', 2) AS INTEGER) as age_max,
    CAST(SPLIT_PART(icmsd.term_slab, 'TO', 1) AS INTEGER) as tenure_min_months,
    CAST(SPLIT_PART(icmsd.term_slab, 'TO', 2) AS INTEGER) as tenure_max_months,
    CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 1) AS DECIMAL) as amount_min,
    CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 2) AS DECIMAL) as amount_max,
    CASE 
        WHEN 25 > CAST(SPLIT_PART(icmsd.age_slab, 'TO', 1) AS INTEGER)  -- Replace 25 with input age
             AND 25 <= CAST(SPLIT_PART(icmsd.age_slab, 'TO', 2) AS INTEGER)
             AND 36 > CAST(SPLIT_PART(icmsd.term_slab, 'TO', 1) AS INTEGER)  -- Replace 36 with input tenure
             AND 36 <= CAST(SPLIT_PART(icmsd.term_slab, 'TO', 2) AS INTEGER)
             AND 100000.00 > CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 1) AS DECIMAL)  -- Replace 100000.00 with input amount
             AND 100000.00 <= CAST(SPLIT_PART(icmsd.amount_slab, 'TO', 2) AS DECIMAL)  -- Replace 100000.00 with input amount
        THEN 'MATCHES'
        ELSE 'NO MATCH'
    END as match_status
FROM insurance_calculation_matrix_slab_details icmsd
WHERE icmsd.premium_calculation_id = (
    SELECT pcd.id 
    FROM premium_calculation_details pcd
    INNER JOIN insurance_product ip ON ip.premium_calculation_code = pcd.code
    INNER JOIN product p ON p.id = ip.product_id
    WHERE p.code = 'INSPro841837'  -- Replace with your product code
      AND ip.is_deleted = false
)
  AND icmsd.gender = 'MALE'         -- Replace with input gender
  AND icmsd.term_unit = 'MONTH'     -- Assuming term_unit is 'MONTH'
  AND icmsd.is_deleted = false;

