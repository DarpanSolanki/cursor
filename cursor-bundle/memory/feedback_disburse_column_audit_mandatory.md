# Disburse / money API — column audit mandatory (2026-07-20)

Darpan: full columns audit across disbursement — correct values in applicable tables/columns
(not presence-only, not status-200). Applies to any API / money-path testing in this workspace.

## Bar

1. Real `disburseLoan` (or domain API/batch) — no service-code hacks for green tests.
2. Value-level asserts via `scripts/disbursement/disbursement_suite/column_audit.py` wired into
   `disburse_loan_sanity.py` — FAIL on wrong values.
3. Registry `disbursement.{quick,jlg,shg,indl,any}` declare `acceptance.db_asserts` covering
   `domain_money_tables.disbursement` in `acceptance_coverage_manifest.json`.
4. Unified entry: `PRODUCT_TYPE=INDL|JLG|SHG bash scripts/bin/disburse-any-quick.sh`.

## Tables (disbursement domain)

loan_account · loan_installment_details · loan_due_details · loan_disbursement_mode_details ·
loan_disbursement_transaction · transaction_master · client_request_response_log

## SHG fixture gotcha

Member `disbursement_repayment_account_details` must include usable `REP_ACCT` when
`repayment_mode=DIRDR` — else CLB recreate throws 130142 (`repayment_account_number is mandatory`).
Suite seeds member mandates **without** `group_id` (parent alone owns group mandate) — duplicate
ACTIVE rows for the same `group_id` break `findRegistrationPendingOrActiveMandateForGroupId`
(NonUniqueResultException → stuck `LAN_CREATED`). Suite fires `childLoanEventProcessingBatchJob`;
schedule asserts on children; drive OK when children are COMPLETED even if one CLMT lags `P`.

Verified local (2026-07-20): JLG/INDL/SHG `suite_ok=True` with `column_audit` FAIL-closed.