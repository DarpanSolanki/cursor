-- =============================================================================
-- QA DPI cleanup — mfi_accounting (database: mfi_qa1 on QA1)
-- =============================================================================
-- Run in DBeaver/psql against the QA DB you are fixing (qa1, qa2, …).
-- Order: Steps 1–4 (transactions) → Step 5 (dpi_accrual_details) → Step 6 (verify).
--
-- Optional: wrap steps 1–5 in BEGIN; … COMMIT;  use ROLLBACK; if counts look wrong.
-- =============================================================================

\set ON_ERROR_STOP on

-- -----------------------------------------------------------------------------
-- STEP 0 — Preflight (how many transaction_master rows match DPI refs)
-- -----------------------------------------------------------------------------
SELECT COUNT(DISTINCT tm.id) AS dpi_linked_transaction_count
FROM mfi_accounting.transaction_master tm
WHERE tm.reference_number IN (
    SELECT accrual_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE accrual_transaction_ref_number IS NOT NULL
    UNION
    SELECT billing_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE billing_transaction_ref_number IS NOT NULL
);

SELECT COUNT(*) AS dpi_accrual_details_rows
FROM mfi_accounting.dpi_accrual_details;

-- =============================================================================
-- TRANSACTION TABLES — DELETE (DPI-linked refs only)
-- Must delete children before transaction_master (FK).
-- =============================================================================

-- STEP 1 — transaction_partition_details (usually blocks master delete if skipped)
DELETE FROM mfi_accounting.transaction_partition_details
WHERE transaction_id IN (
    SELECT tm.id
    FROM mfi_accounting.transaction_master tm
    WHERE tm.reference_number IN (
        SELECT accrual_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE accrual_transaction_ref_number IS NOT NULL
        UNION
        SELECT billing_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE billing_transaction_ref_number IS NOT NULL
    )
);

-- STEP 2 — transaction_metadata
DELETE FROM mfi_accounting.transaction_metadata
WHERE transaction_id IN (
    SELECT tm.id
    FROM mfi_accounting.transaction_master tm
    WHERE tm.reference_number IN (
        SELECT accrual_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE accrual_transaction_ref_number IS NOT NULL
        UNION
        SELECT billing_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE billing_transaction_ref_number IS NOT NULL
    )
);

-- STEP 3 — transaction_details
DELETE FROM mfi_accounting.transaction_details
WHERE transaction_id IN (
    SELECT tm.id
    FROM mfi_accounting.transaction_master tm
    WHERE tm.reference_number IN (
        SELECT accrual_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE accrual_transaction_ref_number IS NOT NULL
        UNION
        SELECT billing_transaction_ref_number
        FROM mfi_accounting.dpi_accrual_details
        WHERE billing_transaction_ref_number IS NOT NULL
    )
);

-- STEP 4 — transaction_master (parent — run last among transaction tables)
DELETE FROM mfi_accounting.transaction_master
WHERE reference_number IN (
    SELECT accrual_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE accrual_transaction_ref_number IS NOT NULL
    UNION
    SELECT billing_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE billing_transaction_ref_number IS NOT NULL
);

-- =============================================================================
-- dpi_accrual_details — pick ONE of A or B (not both)
-- =============================================================================

-- STEP 5A — DELETE all DPI accrual rows
DELETE FROM mfi_accounting.dpi_accrual_details;

-- STEP 5B — TRUNCATE (faster empty table; use instead of 5A if you prefer)
-- TRUNCATE TABLE mfi_accounting.dpi_accrual_details;

-- =============================================================================
-- STEP 6 — Verify
-- =============================================================================
SELECT COUNT(*) AS remaining_dpi_linked_transactions
FROM mfi_accounting.transaction_master tm
WHERE tm.reference_number IN (
    SELECT accrual_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE accrual_transaction_ref_number IS NOT NULL
    UNION
    SELECT billing_transaction_ref_number
    FROM mfi_accounting.dpi_accrual_details
    WHERE billing_transaction_ref_number IS NOT NULL
);

SELECT COUNT(*) AS remaining_dpi_accrual_details_rows
FROM mfi_accounting.dpi_accrual_details;
