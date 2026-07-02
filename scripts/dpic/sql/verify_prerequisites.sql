-- Read-only checks before DPIC local dev test. Exits non-zero on hard blockers.
\set loan_product_id 2886
\set product_id 6367
\set dpi_scheme_id 2655

\set ON_ERROR_STOP on

\echo '=== DPIC verify_prerequisites ==='

DO $$
DECLARE
  n int;
  missing text := '';
BEGIN
  -- Platform DPI catalogues (Flyway / initial-setup — not local inventions)
  SELECT count(*) INTO n FROM mfi_accounting.transaction_catalogue
  WHERE id BETWEEN 1327 AND 1332 AND is_deleted = false;
  IF n < 6 THEN
    RAISE EXCEPTION 'BLOCKER: expected 6 platform DPI catalogues (1327–1332), found %', n;
  END IF;

  -- Product-document accounting rules on EOD catalogues
  SELECT count(*) INTO n
  FROM mfi_accounting.transaction_accounting_rule tar
  WHERE tar.transaction_catalogue_id IN (1327, 1328, 1329, 1330) AND tar.is_deleted = false;
  IF n < 4 THEN
    RAISE EXCEPTION 'BLOCKER: run seed_accounting_rules_from_product_doc.sql first (EOD TAR count=%)', n;
  END IF;

  -- Scheme DPI applicable
  SELECT count(*) INTO n FROM mfi_accounting.product_scheme_frequency_details
  WHERE product_scheme_id = 2655 AND dpi_applicable = 'YES' AND is_deleted = false;
  IF n = 0 THEN
    RAISE EXCEPTION 'BLOCKER: scheme 2655 missing dpi_applicable=YES on frequency row';
  END IF;

  -- Loan product modes
  IF NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_product_allowed_disbursement_modes WHERE loan_product_id = 2886 AND disbursement_mode = 'ACCTWB') THEN
    missing := missing || ' ACCTWB';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM mfi_accounting.loan_product_allowed_repayment_modes WHERE loan_product_id = 2886 AND repayment_mode = 'DIRDR') THEN
    missing := missing || ' DIRDR';
  END IF;
  IF missing <> '' THEN
    RAISE EXCEPTION 'BLOCKER: loan_product 2886 missing modes:% — run setup_local_dev_product_6367.sql', missing;
  END IF;

  -- Product catalogue links
  IF (SELECT count(*) FROM mfi_accounting.product__transaction_catalogue WHERE product_id = 6367 AND transaction_catalogue_id = 1 AND is_deleted = false) = 0 THEN
    RAISE EXCEPTION 'BLOCKER: product 6367 not linked to LOAN_DISBURSEMENT catalogue (id 1)';
  END IF;
  IF (SELECT count(*) FROM mfi_accounting.product__transaction_catalogue WHERE product_id = 6367 AND transaction_catalogue_id BETWEEN 1327 AND 1330 AND is_deleted = false) < 4 THEN
    RAISE EXCEPTION 'BLOCKER: product 6367 missing DPI EOD catalogue links (1327–1330)';
  END IF;

  RAISE NOTICE 'OK: platform catalogues, product-doc TARs, scheme DPI, modes, product links';
END $$;

\echo '--- optional warnings (booking may still fail) ---'
SELECT 'DPI placeholders on product 6367' AS check,
       count(*) AS rows
FROM mfi_accounting.product_transaction_catalogue__placeholder__iad p
JOIN mfi_accounting.product__transaction_catalogue ptc ON ptc.id = p.product_transaction_catalogue_id
WHERE ptc.product_id = 6367 AND ptc.transaction_catalogue_id BETWEEN 1327 AND 1330 AND p.is_deleted = false;
