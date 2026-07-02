# `mfi_accounting` — schema cheatsheet (top tables across the LMS)

> Quick reference for column names + types so DB triage doesn't restart with `information_schema` queries every session. Verified against QA3 Yugabyte 2024.2.5.0 on 2026-05-07. Drives the canned queries in [`db-tools/canned-queries/`](../db-tools/canned-queries/) and the `lan-360` skill.

For full coverage of all 179 tables: [`db-code-map/`](db-code-map/).

## Convention notes

- **Audit cols** on every table: `created_on TIMESTAMP, created_by VARCHAR, updated_on TIMESTAMP, updated_by VARCHAR, is_deleted BOOLEAN`. **No `@PreUpdate`** — `updated_on` is set manually (or by the @Modifying CAS query). See `feedback_no_inmem_mutation_after_cas` memory.
- **PK** is always `id BIGINT GENERATED ALWAYS AS IDENTITY`. Foreign keys are `<entity>_id BIGINT`.
- **No `@Version`** on any of these tables — JPA `save()` is a blind UPDATE. Multi-writer rows use the atomic CAS pattern via `ChildClmtStateMachineService.transition` / `LoanAccountStateMachineService.transition` / `patchJsonFields`.
- All branch dates: `business_date DATE` (LMS business day, not wall-clock); `system_date TIMESTAMP` (wall-clock).

---

## Account / Loan family

### `account` — every Trustt account (LOAN / SAVINGS / GL / INTERNAL)

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `account_number` | VARCHAR | natural key (e.g. `6009683725`) |
| `account_type` | VARCHAR | `LOAN` / `SAVINGS` / `INTERNAL` / `GL` |
| `parent_account_id` | BIGINT | for SHG/JLG children |
| `status` | VARCHAR | `OPEN` / `CLOSED` / etc. |

### `loan_account` — loan-specific properties of LOAN-type accounts

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `account_id` | BIGINT | FK → `account.id` |
| `loan_status` | VARCHAR | `LOAN_BOOKED` / `ACTIVE` / `CLOSED` / `LOCK` / `*_FREEZE` (the state machine) |
| `disbursement_status` | VARCHAR | `DTFC_SUCCESS` / `NEFT_STAGE_1_PENDING` / `NEFT_STAGE_1_SUCCESS` / `NEFT_STAGE_2_PENDING` / `COMPLETED` / `PARENT_SUCCESS` / `CHILD_SUCCESS` |
| `external_ref_number` | VARCHAR | per-leg deterministic ref (NEFT/MFT) |
| `parent_account_id` | BIGINT | redundant with `account.parent_account_id` (per-row convenience) |
| `loan_amount`, `disbursed_amount`, `outstanding_principal`, `outstanding_interest`, `outstanding_dpi*` | NUMERIC | `*dpi*` columns are 3.3.2+ only |
| `past_due_days` | INT | DPD (computed daily by `loanAccountDpdCalcJob`) |
| `npa_ageing_start_date` | DATE | when NPA buckets first triggered |
| `asset_criteria_slabs_id` | BIGINT | FK → `asset_criteria_slabs.id` |
| `disbursement_date`, `maturity_date` | DATE | |
| `filler_1`..`filler_5` | VARCHAR / TEXT | overflow columns; semantics vary per writer (see writer registry in `engines/disbursement-engine.md`) |

### `loan_account_events_queue` — async event fan-out (the most concurrency-fraught table)

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `parent_account_id` | BIGINT | FK → `account.id` (parent SHG/JLG/INDL) |
| `event_type` | VARCHAR | `CLMT` / `CLB` / `REP` / `FCL` / `WAIVER` / `RSTCRE` / `REOPN` / `TXNREV` / `PRTPRE` / `REBK` / `CANCL` / `LEAR` |
| `event_status` | VARCHAR | `P` (pending) / `C` (completed) |
| `data` | TEXT | JSON event payload — query via `(data::jsonb)->>'<key>'`; key `disbursement_status` is the CAS state field for CLMT |
| `event_id` | BIGINT | optional FK to source event |
| `reference_number` | VARCHAR | optional |
| `filler_1`..`filler_5` | TEXT/VARCHAR | semantics: `filler_2` = child external_ref_number on CLMT, `filler_3` = canonical UTR (post-`7ab965fe3`) |

Drained by `childLoanEventProcessingBatchJob` (every 2h, GRID_SIZE=30, CHUNK_SIZE=50). Writer registry (with CAS guards) lives in [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md) §writer-registry.

### `loan_repayment_schedule_details` — installment schedule

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `loan_account_id` | BIGINT | FK → `account.id` of LOAN |
| `installment_number` | INT | |
| `due_date` | DATE | |
| `principal_amount`, `interest_amount`, `total_amount` | NUMERIC | |
| `paid_principal`, `paid_interest` | NUMERIC | |
| `status` | VARCHAR | `PENDING` / `PAID` / `PARTIAL` / `OVERDUE` |

### `loan_account_payments_details` — every payment posted to a loan

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `loan_account_id` | BIGINT | FK |
| `payment_amount` | NUMERIC | |
| `principal_amount`, `interest_amount`, `fee_amount`, `dpi_amount` | NUMERIC | `dpi_amount` is 3.3.2+ |
| `client_reference_number` | VARCHAR | dedup key (CRR / collection receipt) |
| `payment_mode` | VARCHAR | `CASH` / `eNACH` / `SI` / `MANUAL` / etc. |
| `payment_date` | TIMESTAMP | |
| `status` | VARCHAR | |

### `loan_account_billing_details` — billing cycle records

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `loan_account_id` | BIGINT | FK |
| `billing_period_start`, `billing_period_end` | DATE | |
| `principal_billed`, `interest_billed`, `penal_billed`, `fee_billed` | NUMERIC | |

### `loan_account_derived_fields`, `loan_account_derived_fields_monthly`

DPD, NPA, totals, bucket counts. Run by `updateLoanAccountDerivedFieldsJob`. See [`accounting/03-batch-dependency.md`](03-batch-dependency.md).

### `loan_disbursement_mode_details` — disbursement payout details

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `loan_account_id` | BIGINT | FK |
| `utr_number` | VARCHAR | bank UTR (canonical reader: `BookChildLoanProcessor.java:412` from `event.getFiller3()`) |
| `disbursement_mode` | VARCHAR | `NEFT` / `MFT` / `OTHBACCT` / etc. |
| `beneficiary_account_number`, `beneficiary_ifsc` | VARCHAR | |
| `payment_status` | VARCHAR | |

---

## Bank-side audit / idempotency

### `client_request_response_log` (CRR) — every outgoing bank/external API call

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `partner` | VARCHAR | e.g. `Hdfc` |
| `client_reference_number` | VARCHAR | external ref sent to bank |
| `loan_account_number` | VARCHAR | row key for lookups (note: NOT `loan_account_id`) |
| `transaction_type` | VARCHAR | the deterministic key — e.g. `DISBURSEMENT_NEFT_NEF`, `DISBURSEMENT_NEFT_NEI`, `DISBURSEMENT_MFT_REINIT`, `LOAN_DISBURSEMENT_EXTREF<n>_NEFT_NEF` (child); **CONTAINS `_EXTREF` for child rows** |
| `status` | VARCHAR | `SUCCESS` / `FAIL` / `UNKNOWN` |
| `request`, `response` | TEXT | full JSON payloads |
| `system_date`, `business_date` | TIMESTAMP / DATE | |
| `eligible_for_retry`, `retry_count` | BOOL / INT | retry framework hooks |

CRR `save(...)` is `@Transactional(REQUIRES_NEW)` + `@Retryable` — see [`engines/disbursement-engine.md`](../engines/disbursement-engine.md) §5.

---

## Posting / GL

### `transaction_master` — every GL posting (debit + credit pair)

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `transaction_type`, `transaction_subtype` | VARCHAR | drives accounting rule lookup |
| `transaction_status` | VARCHAR | `POSTED` / `REVERSED` / etc. |
| `from_account_id`, `to_account_id` | BIGINT | FK → `account.id` |
| `amount` | NUMERIC | |
| `business_date`, `system_date` | DATE/TIMESTAMP | |
| `client_reference_number` | VARCHAR | dedup key |

### `transaction_metadata` — leg-level breakdown

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `transaction_master_id` | BIGINT | FK |
| `internal_account_id` | BIGINT | FK → `internal_account.id` |
| `cr_dr` | VARCHAR | `CR` / `DR` |
| `amount` | NUMERIC | |

### `transaction_reversal_details` — reversal records

| Column | Type | Notes |
|---|---|---|
| `id` | BIGINT | PK |
| `original_transaction_master_id` | BIGINT | FK to forward txn |
| `reversal_reason` | VARCHAR | |
| `dpi_amount` | NUMERIC | 3.3.2+ |

### `internal_account` / `internal_account_definition` / `general_ledger`

The GL chart of accounts. `internal_account` is the per-tenant instance; `internal_account_definition` is the template; `general_ledger` is the GL master.

### `trial_balance` / `trial_balance_run_history`

EOD-computed balances; net-zero invariant verified by `trialBalanceCalculation` job.

---

## Lifecycle / servicing

| Table | Purpose |
|---|---|
| `loan_account_closure_details` | foreclosure / regular closure record (`closure_type`, `task_id`) |
| `loan_account_part_prepayment_details` | part prepayment (`task_id` for maker-checker) |
| `loan_account_restructuring_details` | restructure (`task_id`) |
| `loan_account_reschedule_details` | reschedule (sibling to restructure) |
| `loan_account_reopening_details` | reopen flow |
| `loan_account_rebooking_details` | rebooking (group loan) |
| `loan_account_excess_amount_refund_details` | excess refund |
| `waiver_details` / `waiver__loan_due_details` | waiver workflow |
| `death_foreclosure_details` + 4 child tables | death foreclosure + insurance |
| `loan_account_charge_details` | per-loan charges (foreclosure / penalty / fees) |
| `loan_account_insurance_details` | per-loan insurance link |
| `loan_account_noc_details` | NOC dispatch |

All servicing tables carry `task_id` when the workflow goes through maker-checker (see [`flows/maker-checker.md`](../flows/maker-checker.md)).

---

## Mandate / SI / collection

| Table | Purpose |
|---|---|
| `enach_presentation_details` | per-cycle eNACH presentation (file-level) |
| `enach_presentation_loan_account_details` | per-LAN row inside a presentation |
| `enach_representation_details`, `enach_representation_loan_account_details` | retry cycle |
| `si_presentation_details`, `si_presentation_file_details`, `si_presentation_loan_account_details` | SI presentation pipe |
| `si_lien_presentation_*` | lien marking presentation |
| `si_manual_hold_*`, `lien_presentation_details` | manual hold marking / removal |
| `si_failed_presentation_details` | failure cycle |
| `bulk_collection_log` | collection ingest audit |

---

## Master data

| Table | Purpose |
|---|---|
| `product`, `product_scheme`, `product__transaction_catalogue` | loan product master |
| `product_scheme_insurance_details` | insurance per product scheme |
| `product_scheme_penal_interest_applicability` | penal applicability |
| `transaction_catalogue`, `transaction_category`, `transaction_accounting_rule` | accounting rule master (post-tx posting) |
| `tax_component`, `tax_group`, `tax_group__tax_component__mapping` | tax setup |
| `interest_setup`, `interest_setup_slab`, `interest_setup_amount_slab`, `interest_setup_date_slab` | interest scheme |
| `base_interest_master`, `base_interest_slab`, `base_interest_date_slab` | base rate scheme |
| `asset_classification_master`, `asset_classification_slabs`, `asset_criteria_master`, `asset_criteria_group`, `asset_criteria_slabs` | NPA / DPD bucket master |
| `holiday`, `holiday_office`, `currency_master` | calendar / currency |
| `placeholder_master` (in `mfi_accounting.placeholder_master`) | accounting-rule placeholders |

---

## Batch / audit / staging

| Table | Purpose |
|---|---|
| `batch_failure_audit` | per-job failure log (used by canned `17-batch-failures-recent.sql`) |
| `accounting_dump` | one-off / debug dump |
| `flyway_schema_history` | migration log |
| `file_staging_*` | inbound file ingestion staging (death-foreclosure, NPA reverse-feed, eNACH representation, manual journal entries, refunds, etc.) |
| `accts_under_pc_180_staging_table`, `accts_under_pc_182_staging_table` | RBI provisioning staging |

---

## Cross-links

- Full per-table coverage: [`db-code-map/`](db-code-map/) — 179 tables indexed by table name + by flow + by Request.
- Writer registry for `loan_account_events_queue`: [`../engines/disbursement-engine.md`](../engines/disbursement-engine.md) §writer-registry.
- Canned diagnostic queries: [`../db-tools/canned-queries/`](../db-tools/canned-queries/).
- Concurrency rules: [`../rules/multi-path-state-persistence-safety.md`](../rules/multi-path-state-persistence-safety.md), `feedback_no_inmem_mutation_after_cas` memory.
