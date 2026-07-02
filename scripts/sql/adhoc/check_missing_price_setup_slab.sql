-- ============================================================================
-- SQL Queries to Check Missing Price Setup Slabs
-- ============================================================================
-- Use these queries to diagnose why a price setup slab is not found
-- Based on error: "Slab is not configured for price setup with code: Penalty_P, 
--                  date: 2025-12-30 and transaction amount: 740194.0"
-- ============================================================================

-- ============================================================================
-- QUERY 1: Check if Price Setup exists
-- ============================================================================
-- Replace 'Penalty_P' with your actual price setup code
SELECT 
    id,
    code,
    name,
    charge_type,
    currency,
    is_deleted,
    created_at,
    updated_at
FROM price_setup
WHERE code = 'Penalty_P'
  AND is_deleted = false;

-- ============================================================================
-- QUERY 2: Check Date Slabs for the Price Setup
-- ============================================================================
-- This shows all date ranges configured for the price setup
-- Replace 'Penalty_P' and '2025-12-30' with your values
SELECT 
    ps.id as price_setup_id,
    ps.code as price_setup_code,
    ps.name as price_setup_name,
    psds.id as date_slab_id,
    psds.start_date,
    psds.end_date,
    psds.is_deleted as date_slab_deleted,
    CASE 
        WHEN '2025-12-30' BETWEEN psds.start_date AND COALESCE(psds.end_date, '9999-12-31') 
        THEN 'YES - Date is covered'
        ELSE 'NO - Date is NOT covered'
    END as date_coverage_status
FROM price_setup ps
LEFT JOIN price_setup_date_slab psds ON ps.id = psds.price_setup_id 
    AND psds.is_deleted = false
WHERE ps.code = 'Penalty_P'
  AND ps.is_deleted = false
ORDER BY psds.start_date;

-- ============================================================================
-- QUERY 3: Check Amount Slabs for a Specific Date
-- ============================================================================
-- This shows all amount slabs for date slabs that cover the transaction date
-- Replace 'Penalty_P', '2025-12-30', and 740194.0 with your values
SELECT 
    ps.code as price_setup_code,
    psds.start_date,
    psds.end_date,
    pss.id as slab_id,
    pss.from_amount,
    pss.to_amount,
    pss.base_amount,
    pss.percentage,
    pss.is_deleted as slab_deleted,
    CASE 
        WHEN 740194.0 BETWEEN pss.from_amount AND COALESCE(pss.to_amount, 999999999999.99)
        THEN 'YES - Amount is covered'
        ELSE 'NO - Amount is NOT covered'
    END as amount_coverage_status,
    CASE 
        WHEN pss.from_amount IS NULL THEN 'ERROR: from_amount is NULL'
        WHEN pss.to_amount IS NULL THEN 'WARNING: to_amount is NULL (may be open-ended)'
        ELSE 'OK'
    END as amount_validation
FROM price_setup ps
INNER JOIN price_setup_date_slab psds ON ps.id = psds.price_setup_id
    AND '2025-12-30' BETWEEN psds.start_date AND COALESCE(psds.end_date, '9999-12-31')
    AND psds.is_deleted = false
LEFT JOIN price_setup_slab pss ON psds.id = pss.price_setup_date_slab_id
    AND pss.is_deleted = false
WHERE ps.code = 'Penalty_P'
  AND ps.is_deleted = false
ORDER BY pss.from_amount;

-- ============================================================================
-- QUERY 4: Comprehensive Check - Find What's Missing
-- ============================================================================
-- This query identifies exactly what's missing for a specific transaction
-- Replace the variables in the CTE with your actual values
WITH transaction_params AS (
    SELECT 
        'Penalty_P' as price_setup_code,
        '2025-12-30'::date as transaction_date,
        740194.0 as transaction_amount
),
price_setup_check AS (
    SELECT 
        tp.*,
        ps.id as price_setup_id,
        ps.code,
        ps.name,
        CASE WHEN ps.id IS NULL THEN 'MISSING: Price Setup does not exist' 
             WHEN ps.is_deleted THEN 'MISSING: Price Setup is deleted'
             ELSE 'OK: Price Setup exists'
        END as price_setup_status
    FROM transaction_params tp
    LEFT JOIN price_setup ps ON ps.code = tp.price_setup_code AND ps.is_deleted = false
),
date_slab_check AS (
    SELECT 
        psc.*,
        psds.id as date_slab_id,
        psds.start_date,
        psds.end_date,
        CASE 
            WHEN psc.price_setup_id IS NULL THEN 'SKIP: Price Setup not found'
            WHEN psds.id IS NULL THEN 'MISSING: No date slab found for transaction date'
            WHEN psc.transaction_date NOT BETWEEN psds.start_date AND COALESCE(psds.end_date, '9999-12-31')
            THEN 'MISSING: Date slab does not cover transaction date'
            WHEN psds.is_deleted THEN 'MISSING: Date slab is deleted'
            ELSE 'OK: Date slab covers transaction date'
        END as date_slab_status
    FROM price_setup_check psc
    LEFT JOIN price_setup_date_slab psds ON psc.price_setup_id = psds.price_setup_id
        AND psc.transaction_date BETWEEN psds.start_date AND COALESCE(psds.end_date, '9999-12-31')
        AND psds.is_deleted = false
),
amount_slab_check AS (
    SELECT 
        dsc.*,
        pss.id as amount_slab_id,
        pss.from_amount,
        pss.to_amount,
        pss.base_amount,
        pss.percentage,
        CASE 
            WHEN dsc.date_slab_id IS NULL THEN 'SKIP: Date slab not found'
            WHEN pss.id IS NULL THEN 'MISSING: No amount slab found for date slab'
            WHEN dsc.transaction_amount NOT BETWEEN pss.from_amount AND COALESCE(pss.to_amount, 999999999999.99)
            THEN 'MISSING: Amount slab does not cover transaction amount'
            WHEN pss.is_deleted THEN 'MISSING: Amount slab is deleted'
            ELSE 'OK: Amount slab covers transaction amount'
        END as amount_slab_status
    FROM date_slab_check dsc
    LEFT JOIN price_setup_slab pss ON dsc.date_slab_id = pss.price_setup_date_slab_id
        AND dsc.transaction_amount BETWEEN pss.from_amount AND COALESCE(pss.to_amount, 999999999999.99)
        AND pss.is_deleted = false
)
SELECT 
    price_setup_code,
    transaction_date,
    transaction_amount,
    price_setup_status,
    date_slab_status,
    amount_slab_status,
    CASE 
        WHEN price_setup_status LIKE 'MISSING%' THEN price_setup_status
        WHEN date_slab_status LIKE 'MISSING%' THEN date_slab_status
        WHEN amount_slab_status LIKE 'MISSING%' THEN amount_slab_status
        ELSE 'OK: All checks passed - slab should be found'
    END as overall_status,
    -- Show existing slabs for reference
    COALESCE(amount_slab_id::text, 'N/A') as found_slab_id,
    COALESCE(from_amount::text, 'N/A') as found_from_amount,
    COALESCE(to_amount::text, 'N/A') as found_to_amount
FROM amount_slab_check;

-- ============================================================================
-- QUERY 5: Find All Amount Slabs for a Price Setup (for reference)
-- ============================================================================
-- This shows all configured slabs to help identify gaps
SELECT 
    ps.code as price_setup_code,
    psds.start_date,
    psds.end_date,
    pss.id as slab_id,
    pss.from_amount,
    pss.to_amount,
    pss.base_amount,
    pss.percentage,
    CASE 
        WHEN pss.to_amount IS NULL THEN CONCAT(pss.from_amount::text, ' to INFINITY')
        ELSE CONCAT(pss.from_amount::text, ' to ', pss.to_amount::text)
    END as amount_range,
    CASE 
        WHEN pss.base_amount IS NOT NULL AND pss.base_amount > 0 THEN 'FLAT: ' || pss.base_amount::text
        WHEN pss.percentage IS NOT NULL THEN 'PERCENTAGE: ' || pss.percentage::text || '%'
        ELSE 'NOT CONFIGURED'
    END as charge_type
FROM price_setup ps
INNER JOIN price_setup_date_slab psds ON ps.id = psds.price_setup_id
    AND psds.is_deleted = false
LEFT JOIN price_setup_slab pss ON psds.id = pss.price_setup_date_slab_id
    AND pss.is_deleted = false
WHERE ps.code = 'Penalty_P'
  AND ps.is_deleted = false
ORDER BY psds.start_date, pss.from_amount;

-- ============================================================================
-- QUERY 6: Find Gaps in Amount Coverage for a Specific Date
-- ============================================================================
-- This helps identify if there are gaps in amount ranges
WITH date_slabs AS (
    SELECT 
        ps.id as price_setup_id,
        ps.code,
        psds.id as date_slab_id,
        psds.start_date,
        psds.end_date
    FROM price_setup ps
    INNER JOIN price_setup_date_slab psds ON ps.id = psds.price_setup_id
    WHERE ps.code = 'Penalty_P'
      AND '2025-12-30' BETWEEN psds.start_date AND COALESCE(psds.end_date, '9999-12-31')
      AND ps.is_deleted = false
      AND psds.is_deleted = false
),
amount_slabs AS (
    SELECT 
        ds.*,
        pss.id as slab_id,
        pss.from_amount,
        pss.to_amount,
        LAG(pss.to_amount) OVER (PARTITION BY ds.date_slab_id ORDER BY pss.from_amount) as prev_to_amount
    FROM date_slabs ds
    LEFT JOIN price_setup_slab pss ON ds.date_slab_id = pss.price_setup_date_slab_id
        AND pss.is_deleted = false
)
SELECT 
    code,
    start_date,
    end_date,
    from_amount,
    to_amount,
    prev_to_amount,
    CASE 
        WHEN prev_to_amount IS NOT NULL 
             AND from_amount > prev_to_amount 
             AND to_amount IS NOT NULL
        THEN CONCAT('GAP FOUND: ', prev_to_amount::text, ' to ', from_amount::text)
        WHEN from_amount IS NULL THEN 'ERROR: from_amount is NULL'
        WHEN to_amount IS NULL THEN 'OPEN-ENDED: No upper limit'
        ELSE 'OK: Continuous coverage'
    END as gap_status
FROM amount_slabs
ORDER BY from_amount NULLS LAST;

-- ============================================================================
-- USAGE INSTRUCTIONS
-- ============================================================================
-- 1. Replace 'Penalty_P' with your actual price setup code
-- 2. Replace '2025-12-30' with your actual transaction date
-- 3. Replace 740194.0 with your actual transaction amount
-- 4. Run Query 4 first for a comprehensive diagnosis
-- 5. Use Query 5 to see all configured slabs
-- 6. Use Query 6 to identify gaps in amount coverage
-- ============================================================================




