-- Local dev setup for product 6367 / loan_product 2886 / DPI scheme 300 (id 2655).
--
-- Purpose: restore a working LMS disburse + DPI calc path on an incomplete QA dump.
-- Does NOT create transaction_catalogue rows — only links existing platform catalogues
-- and maps placeholder codes from the DPI v1.3 product document to local IADs.
--
-- Run AFTER: scripts/dpic/sql/seed_accounting_rules_from_product_doc.sql
--
-- Sections:
--   A  QA loan-product modes (ACCTWB / DIRDR)
--   B  Link standard MFI loan catalogues 1–6 to product (platform ids)
--   C  Disbursement placeholder IADs (catalogue 1) from reference product 6067
--   D  Interest/NPA placeholder IADs (catalogues 2–6) from reference product 2
--   E  Link DPI EOD catalogues 1327–1330 (platform ids per product doc)
--   F  DPI placeholder codes → local IAD mapping (document codes; QA GL ids)
--   G  Scheme 2655: DPI_EOD on TAR rules + catalogue price_setup

\set loan_product_id 2886
\set product_id 6367
\set dpi_scheme_id 2655
\set ref_disburse_product_id 6067
\set ref_standard_product_id 2

BEGIN;

-- A) Production-like disbursement / repayment modes (QA dump had CASH only)
INSERT INTO mfi_accounting.loan_product_allowed_disbursement_modes (disbursement_mode, loan_product_id)
SELECT m, :loan_product_id
FROM (VALUES ('ACCTWB'), ('OTHBACCT')) AS v(m)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.loan_product_allowed_disbursement_modes x
  WHERE x.loan_product_id = :loan_product_id AND x.disbursement_mode = v.m
);

INSERT INTO mfi_accounting.loan_product_allowed_repayment_modes (repayment_mode, loan_product_id)
SELECT 'DIRDR', :loan_product_id
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.loan_product_allowed_repayment_modes x
  WHERE x.loan_product_id = :loan_product_id AND x.repayment_mode = 'DIRDR'
);

-- B) Link standard loan catalogues (platform) — not DPI-specific inventions
INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT :product_id, src.transaction_catalogue_id, NOW(), 'DPIC_LOCAL_DEV', NOW(), 'DPIC_LOCAL_DEV', false
FROM mfi_accounting.product__transaction_catalogue src
WHERE src.product_id = :ref_standard_product_id AND src.is_deleted = false
  AND src.transaction_catalogue_id BETWEEN 1 AND 6
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
    WHERE t.product_id = :product_id
      AND t.transaction_catalogue_id = src.transaction_catalogue_id
      AND t.is_deleted = false
  );

-- C) LOAN_DISBURSEMENT (cat 1) placeholders — stamp/GST/PROC_FEE from reference product 6067
UPDATE mfi_accounting.product_transaction_catalogue__placeholder__iad p
SET internal_account_definition_id = src.internal_account_definition_id,
    is_deleted = false
FROM mfi_accounting.product__transaction_catalogue tgt_ptc
JOIN mfi_accounting.product__transaction_catalogue src_ptc
  ON src_ptc.product_id = :ref_disburse_product_id
 AND src_ptc.transaction_catalogue_id = 1
 AND src_ptc.is_deleted = false
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad src
  ON src.product_transaction_catalogue_id = src_ptc.id
 AND src.is_deleted = false
WHERE p.product_transaction_catalogue_id = tgt_ptc.id
  AND tgt_ptc.product_id = :product_id
  AND tgt_ptc.transaction_catalogue_id = 1
  AND tgt_ptc.is_deleted = false
  AND p.placeholder_code = src.placeholder_code
  AND p.is_deleted = false;

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT tgt_ptc.id, src.placeholder_code, src.internal_account_definition_id, false
FROM mfi_accounting.product__transaction_catalogue tgt_ptc
JOIN mfi_accounting.product__transaction_catalogue src_ptc
  ON src_ptc.product_id = :ref_disburse_product_id
 AND src_ptc.transaction_catalogue_id = 1
 AND src_ptc.is_deleted = false
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad src
  ON src.product_transaction_catalogue_id = src_ptc.id
 AND src.is_deleted = false
WHERE tgt_ptc.product_id = :product_id
  AND tgt_ptc.transaction_catalogue_id = 1
  AND tgt_ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = tgt_ptc.id
      AND x.placeholder_code = src.placeholder_code
      AND x.is_deleted = false
  );

-- D) Catalogues 2–6 placeholders from reference product 2
UPDATE mfi_accounting.product_transaction_catalogue__placeholder__iad p
SET internal_account_definition_id = src.internal_account_definition_id,
    is_deleted = false
FROM mfi_accounting.product__transaction_catalogue tgt_ptc
JOIN mfi_accounting.product__transaction_catalogue src_ptc
  ON src_ptc.product_id = :ref_standard_product_id
 AND src_ptc.transaction_catalogue_id = tgt_ptc.transaction_catalogue_id
 AND src_ptc.is_deleted = false
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad src
  ON src.product_transaction_catalogue_id = src_ptc.id
 AND src.is_deleted = false
WHERE p.product_transaction_catalogue_id = tgt_ptc.id
  AND tgt_ptc.product_id = :product_id
  AND tgt_ptc.transaction_catalogue_id BETWEEN 2 AND 6
  AND tgt_ptc.is_deleted = false
  AND p.placeholder_code = src.placeholder_code
  AND p.is_deleted = false;

INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT tgt_ptc.id, src.placeholder_code, src.internal_account_definition_id, false
FROM mfi_accounting.product__transaction_catalogue tgt_ptc
JOIN mfi_accounting.product__transaction_catalogue src_ptc
  ON src_ptc.product_id = :ref_standard_product_id
 AND src_ptc.transaction_catalogue_id = tgt_ptc.transaction_catalogue_id
 AND src_ptc.is_deleted = false
JOIN mfi_accounting.product_transaction_catalogue__placeholder__iad src
  ON src.product_transaction_catalogue_id = src_ptc.id
 AND src.is_deleted = false
WHERE tgt_ptc.product_id = :product_id
  AND tgt_ptc.transaction_catalogue_id BETWEEN 2 AND 6
  AND tgt_ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = tgt_ptc.id
      AND x.placeholder_code = src.placeholder_code
      AND x.is_deleted = false
  );

-- PROC_FEE on disburse catalogue if still missing
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, 'PROC_FEE', 71, false
FROM mfi_accounting.product__transaction_catalogue ptc
WHERE ptc.product_id = :product_id AND ptc.transaction_catalogue_id = 1 AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id AND x.placeholder_code = 'PROC_FEE' AND x.is_deleted = false
  );

-- E) Link DPI EOD catalogues from product doc (platform ids 1327–1330)
INSERT INTO mfi_accounting.product__transaction_catalogue
    (product_id, transaction_catalogue_id, created_on, created_by, updated_on, updated_by, is_deleted)
SELECT :product_id, tc_id, NOW(), 'DPIC_LOCAL_DEV', NOW(), 'DPIC_LOCAL_DEV', false
FROM (VALUES (1327), (1328), (1329), (1330)) AS v(tc_id)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product__transaction_catalogue t
  WHERE t.product_id = :product_id AND t.transaction_catalogue_id = v.tc_id AND t.is_deleted = false
);

-- F) DPI placeholder codes (from xlsx / transaction_accounting_rule) → local QA IAD ids
--    Replace when Ops delivers product-6367 GL mapping.
INSERT INTO mfi_accounting.product_transaction_catalogue__placeholder__iad
    (product_transaction_catalogue_id, placeholder_code, internal_account_definition_id, is_deleted)
SELECT ptc.id, m.placeholder_code, m.iad_id, false
FROM mfi_accounting.product__transaction_catalogue ptc
JOIN (VALUES
  (1327, 'LOAN_ACCOUNT',         28),
  (1327, 'DPI_ACC_NOT_DUE',       5),
  (1327, 'DPI_INT_INC',           6),
  (1328, 'LOAN_ACCOUNT',         28),
  (1328, 'DPI_ACC_NOT_DUE',       5),
  (1328, 'DPI_INT_SUSP_AIR',     12),
  (1329, 'LOAN_ACCOUNT',         28),
  (1329, 'DPI_INT_SUSP_AIR',     12),
  (1329, 'DPI_INT_SUSP',          8),
  (1330, 'LOAN_ACCOUNT',         28),
  (1330, 'DPI_ACC_NOT_DUE',       5),
  (1330, 'DPI_BILLED_INTEREST', 6293)
) AS m(cat_id, placeholder_code, iad_id) ON m.cat_id = ptc.transaction_catalogue_id
WHERE ptc.product_id = :product_id AND ptc.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_transaction_catalogue__placeholder__iad x
    WHERE x.product_transaction_catalogue_id = ptc.id
      AND x.placeholder_code = m.placeholder_code
      AND x.is_deleted = false
  );

-- G1) Scheme → document TAR rules (DPI_EOD) for catalogues 1327–1330
INSERT INTO mfi_accounting.product_scheme__transaction_accounting_rule__price_setup
    (product_scheme_id, transaction_accounting_rule_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :dpi_scheme_id, tar.id, 'DPI_EOD', false, NOW(), 'DPIC_LOCAL_DEV'
FROM mfi_accounting.transaction_accounting_rule tar
JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
WHERE tc.id IN (1327, 1328, 1329, 1330)
  AND tar.is_deleted = false
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup x
    WHERE x.product_scheme_id = :dpi_scheme_id
      AND x.transaction_accounting_rule_id = tar.id
      AND x.is_deleted = false
  );

-- G2) PROC_FEE disburse rule on scheme (standard MFI)
INSERT INTO mfi_accounting.product_scheme__transaction_accounting_rule__price_setup
    (product_scheme_id, transaction_accounting_rule_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :dpi_scheme_id, 135, 'PROC_FEE', false, NOW(), 'DPIC_LOCAL_DEV'
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup x
  WHERE x.product_scheme_id = :dpi_scheme_id
    AND x.transaction_accounting_rule_id = 135
    AND x.price_setup_code = 'PROC_FEE'
    AND x.is_deleted = false
);

-- G3) Scheme catalogue price_setup (DPI_EOD on catalogues 1327–1330)
INSERT INTO mfi_accounting.product_scheme__transaction_catalogue__price_setup
    (product_scheme_id, transaction_catalogue_id, price_setup_code, is_deleted, updated_on, updated_by)
SELECT :dpi_scheme_id, tc_id, 'DPI_EOD', false, NOW(), 'DPIC_LOCAL_DEV'
FROM (VALUES (1327), (1328), (1329), (1330)) AS v(tc_id)
WHERE NOT EXISTS (
  SELECT 1 FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup x
  WHERE x.product_scheme_id = :dpi_scheme_id
    AND x.transaction_catalogue_id = v.tc_id
    AND x.price_setup_code = 'DPI_EOD'
    AND x.is_deleted = false
);

COMMIT;

\echo '=== setup_local_dev_product_6367.sql summary ==='
SELECT disbursement_mode FROM mfi_accounting.loan_product_allowed_disbursement_modes WHERE loan_product_id=:loan_product_id ORDER BY 1;
SELECT repayment_mode FROM mfi_accounting.loan_product_allowed_repayment_modes WHERE loan_product_id=:loan_product_id ORDER BY 1;
SELECT count(*) AS product_catalogues FROM mfi_accounting.product__transaction_catalogue WHERE product_id=:product_id AND is_deleted=false;
SELECT count(*) AS dpi_catalogue_links FROM mfi_accounting.product__transaction_catalogue WHERE product_id=:product_id AND transaction_catalogue_id BETWEEN 1327 AND 1330 AND is_deleted=false;
SELECT count(*) AS dpi_eod_tar_rules FROM mfi_accounting.product_scheme__transaction_accounting_rule__price_setup ps
JOIN mfi_accounting.transaction_accounting_rule tar ON tar.id=ps.transaction_accounting_rule_id
WHERE ps.product_scheme_id=:dpi_scheme_id AND ps.is_deleted=false AND ps.price_setup_code='DPI_EOD';
SELECT count(*) AS dpi_eod_cat_price_setup FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup
WHERE product_scheme_id=:dpi_scheme_id AND price_setup_code='DPI_EOD' AND is_deleted=false;
