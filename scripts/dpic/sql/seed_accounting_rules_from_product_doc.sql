-- DPI transaction_accounting_rule seed from product document:
--   "Sample Calculation and Accounting Entries of DPI v 1.3.xlsx"
--
-- Inserts global rules only (transaction_accounting_rule). Does NOT create
-- transaction_catalogue rows — those exist in platform seed (ids 1327–1332).
--
-- Catalogue mapping (sheet New Id → local DB):
--   New Id_1..6 → 1327, 1330, 1331, 1332, 1328, 1329
--   108→3, 110→4, 115→327, 116→10, 117→11, 209→429
--   109 (LOAN_REPAYMENT CASA) skipped — not in local catalogue
--
-- Run from workspace root:
--   psql ... -v ON_ERROR_STOP=1 -f scripts/dpic/sql/seed_accounting_rules_from_product_doc.sql

\set ON_ERROR_STOP on
\ir dpi_accounting_rules_insert.sql
