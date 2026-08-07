# 09 · Accounting / LMS data model (table map)

> **Schema:** `mfi_accounting` (per [01-overview.md §service coordinates](01-overview.md#service-coordinates)). Spring Batch meta-tables (`BATCH_JOB_INSTANCE`, etc.) live in the same datasource but in default Spring Batch tables.
>
> **Why this file:** the entity list in `01-overview.md` is alphabetical but doesn't show *how the tables relate*. This page groups tables by responsibility, names the JPA entity that maps to each, and shows the keys that wire them together. Use it before writing any SQL or migration against the LMS schema.

---

## 1. Master groups at a glance

```
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│  PRODUCT MASTERS                LOAN ACCOUNT             SERVICING DETAILS                  │
│  product / product_scheme       account ─┬─ loan_account ┬─ loan_installment_details        │
│  loan_product                            │               ├─ loan_due_details                │
│  product_transaction_catalogue           │               ├─ loan_repayment_schedule_details │
│  loan_product_asset_criteria             │               ├─ loan_account_payments_details   │
│                                          │               ├─ loan_account_billing_details    │
│  PRICING / TAX / INTEREST                │               ├─ loan_account_charge_details     │
│  price_master / price_setup              │               ├─ loan_account_tax_details        │
│  tax_component / tax_group               │               ├─ loan_account_derived_fields(_monthly) │
│  base_interest_master / _slab            │               ├─ loan_account_part_prepayment_details │
│  interest_setup / _slab                  │               ├─ loan_account_reschedule_details │
│                                          │               ├─ loan_account_restructuring_details │
│  GL / INTERNAL ACCOUNTS                  │               ├─ loan_account_rebooking_details  │
│  general_ledger / child_general_ledger   │               ├─ loan_account_reopening_details  │
│  internal_account_definition             │               ├─ loan_account_closure_details    │
│  internal_account                        │               ├─ loan_account_excess_amount_refund_details │
│  placeholder_master                      │               ├─ loan_account_noc_details        │
│                                          │               ├─ loan_account_insurance_details  │
│  ACCOUNTING RULES                        │               ├─ loan_account_nominee_details    │
│  transaction_catalogue                   │               ├─ loan_provisioning_details       │
│  transaction_accounting_rule             │               └─ loan_account_events_queue       │
│  product_transaction_catalogue_*         │                  (parent/child queue — §3)       │
│                                          │                                                  │
│  ASSET CLASSIFICATION (NPA)              │  TRANSACTION (THE LEDGER)                       │
│  asset_classification_master / _slabs    │  transaction_master                             │
│  asset_criteria_master / _slabs          │  transaction_partition_details                  │
│  asset_criteria_group                    │  transaction_metadata                           │
│                                          │  transaction_details (per-account rows)         │
│  EOD/BOD ARTIFACTS                       │  transaction_reversal_document                  │
│  trial_balance / trial_balance_run_history                                                 │
│  interest_accrual_details                                                                  │
│  penal_interest_accrual_details                                                            │
│                                                                                             │
│  DISBURSEMENT MECHANICS                  STAGING / BULK FILES                              │
│  loan_disbursement_transaction           file_staging_dispatch_details                     │
│  loan_disbursement_charge_details        file_staging_finsall_repayment                    │
│  loan_disbursement_mode_details          file_staging_manual_hold_marking                  │
│  loan_disbursement_cancellation_*        file_staging_post_disbursement_insurance          │
│  bank_service_call_retry                 file_staging_sec_npa_reverse_feed_file            │
│                                                                                             │
│  MANDATES                                INSURANCE / DEATH FORECLOSURE                     │
│  enach_presentation_*                    insurance_product / *_calculation_matrix_*        │
│  enach_representation_*                  insurance_not_applicable_states                   │
│  si_presentation_* / si_*_hold_*         death_foreclosure_* (claim, nominee, payment)     │
│  si_failed_presentation_details                                                            │
│                                                                                             │
│  MISC                                                                                      │
│  holiday / holiday_office / working_days_master / working_days                             │
│  stamp_duty_master / stamp_duty_statewise_details                                          │
│  manual_journal_entry_* (bulk JE flows)                                                    │
│  waiver_*                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
```

(Comprehensive entity-list reference: the table in `/home/darpan/Documents/sliProd/trustt-platform-accounting/.cursorrules` ships with the service.)

---

## 2. The "loan account" cluster — the heart of LMS

### Inheritance

`AccountEntity` is `@Inheritance(InheritanceType.JOINED)`. There is one `account` row and one `loan_account` row per loan. The two share `account.id = loan_account.account_id`. SQL nearly always joins them.

```sql
SELECT a.id, a.account_number, a.parent_account_id, la.loan_status, la.loan_product_id
  FROM mfi_accounting.account a
  JOIN mfi_accounting.loan_account la ON la.account_id = a.id
 WHERE a.account_number = ?;
```

### Direct child tables (FK = `loan_account.account_id` unless noted)

| Table | Entity | Purpose |
|---|---|---|
| `loan_installment_details` | `LoanInstallmentDetailsEntity` | The contractual EMI schedule (one row per installment, components stored as columns or flattened) |
| `loan_due_details` | `LoanDueDetailsEntity` | Per-component pending/paid amounts, with `due_date`, `component_type` (`PRIN`/`INT`/`PINT`/`FEE`), `due_amount`, `paid_amount`, `waived_amount`, `current_paid_amount` (transient during a repayment). **This is the table the appropriation algorithm walks.** |
| `loan_repayment_schedule_details` | (same shape as installment details, used as the master immutable schedule) | Stored at disbursement time; not modified post-disbursement except by reschedule/restructure |
| `loan_account_billing_details` | `LoanAccountBillingDetailsEntity` | The "due" rows materialised by `loanAccountBillingJob` each EOD — a snapshot for collections/dunning |
| `loan_account_payments_details` | `LoanAccountPaymentsDetailsEntity` | Every settled payment (one row per `loanRepayment` call), with `excess_amount` carried forward |
| `loan_account_charge_details` | charge entity | Configured charges (PriceSetup) bound to the account |
| `loan_account_tax_details` | tax entity | Tax components applied per charge |
| `loan_account_part_prepayment_details` | `LoanAccountPartPrepaymentDetailsEntity` | One row per part-prepayment event (with proposed/applied schedule diff) |
| `loan_account_reschedule_details` | reschedule entity | Pending/applied reschedule events from `registerLoanAccountRescheduleEvent` |
| `loan_account_restructuring_details` | restructuring entity | Restructure proposals + final state |
| `loan_account_rebooking_details` | rebooking entity | Group/individual rebooking events |
| `loan_account_reopening_details` | reopening entity | History of any closure-reversals |
| `loan_account_closure_details` | closure entity | One row per close-event (foreclosure, write-off, auto-close); kept around so `loanAccountReopening` can rebuild |
| `loan_account_excess_amount_refund_details` | refund entity | Excess-amount refund initiations |
| `loan_account_noc_details` | noc entity | NOC issued/blocked status per loan |
| `loan_account_insurance_details` | insurance entity | Bound insurance products + premium amounts |
| `loan_account_nominee_details` | nominee entity | Nominee for the loan (death-fc input) |
| `loan_account_derived_fields` | denormalised denorm | Daily-refreshed snapshot (DPD, outstanding, NPA bucket) for fast reporting |
| `loan_account_derived_fields_monthly` | denorm | Monthly version (slower-moving fields: provisioning, classification history) |
| `loan_provisioning_details` | provisioning entity | Per-loan provisioning amount derived from asset classification |
| `loan_account_events_queue` | `LoanAccountEventsQueueEntity` | The async event queue for SHG/JLG parent→child fan-out (see [06-shg-jlg-group-loans.md](06-shg-jlg-group-loans.md)) |

### Derived / computed columns on `loan_account` itself

(See [LoanAccountEntity.java](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java))

- `past_due_days` — current DPD (refreshed by `loanAccountDpdCalcJob`)
- `asset_criteria_group_id`, `asset_criteria_slabs_id` — current NPA bucket reference
- `disbursement_status` — orthogonal to `loan_status`, drives the `disburseLoan` state machine
- `npa_ageing_start_date` — first date the loan crossed the NPA threshold
- `fraction` — child-loan share of parent EMI (null on parent)

---

## 3. SHG/JLG parent ↔ child wiring

```
account (parent)                         account (child 1)              account (child 2)  …
  id          = 100                        id              = 201           id              = 202
  parent_account_id = NULL                 parent_account_id = 100         parent_account_id = 100
  account_number    = 'GLN0001'            account_number    = 'GLN0001-1' account_number    = 'GLN0001-2'
   │                                        │                                │
   │                                        │                                │
loan_account (parent)                    loan_account (child)               loan_account (child)
  account_id = 100                         account_id = 201                  account_id = 202
  fraction   = NULL                        fraction   = 0.5                  fraction   = 0.5
  loan_status = ACTIVE                     loan_status = ACTIVE              loan_status = ACTIVE
   │
   │
loan_account_events_queue (rows for parent.id=100)
  parent_account_id = 100
  event_type = 'CLB' / 'REP' / 'FCL' / …
  event_status = 'P' or 'C'
  data = JSON array, one element per child
```

See [06-shg-jlg-group-loans.md](06-shg-jlg-group-loans.md) for full event-queue semantics.

---

## 4. Product / scheme / pricing — read top-down

```
product (registry)
  ├── loan_product (specialisation; carries product_id)
  │     ├── loan_product_allowed_collaterals
  │     ├── loan_product_allowed_purposes
  │     ├── loan_product_asset_criteria   ← (product_id, asset_criteria_slab_id) → liquidationOrder + 4 component slots
  │     └── loan_product_policy_type
  └── product_scheme (one product can have N schemes)
        ├── product_scheme_transaction_catalogue_price_setup    (binds a transaction's pricing per scheme)
        ├── product_scheme_transaction_accounting_rule_price_setup
        ├── product_scheme_insurance_details
        └── product_scheme_penal_interest_applicability

product_transaction_catalogue           ← which transaction catalogues are applicable to which product type
product_transaction_catalogue_placeholder ← (product_id, transaction_catalogue_id, placeholder_code) → internal_account_definition_id + gl_code
                                          ← THIS is what the GL posting engine uses (see 08)

product_type_placeholder_master         ← which placeholders are valid for which product type
product_type_transaction_catalogue      ← which transaction catalogues are valid for which product type

price_master / price_setup / price_setup_slab  ← charges & fees, slab-based
tax_component / tax_component_slab / tax_group / tax_group_tax_component_mapping  ← tax masters
base_interest_master / base_interest_slab / base_interest_date_slab  ← base rates effective by date
interest_setup / interest_setup_date_slab / interest_setup_slab  ← per-product interest setup overlay on base rate
```

---

## 5. The ledger cluster — what `postTransaction` writes

```
transaction_master                ← txn header (ref no, status, total amount, catalogue id, client_ref_no)
   │
   ├── transaction_metadata       ← key/value bag carried with the txn
   │
   ├── transaction_partition_details   ← N rows per txn (one per leg; gl_code, account_number, cr_dr_indicator,
   │                                      amount, source_amount, narration, part_info_1..3, entity_id, entity_type,
   │                                      child_gl_code (boolean))
   │
   └── transaction_details        ← account-side rows (per affected account_number)
                                      → triggers update on account_balance

transaction_reversal_document     ← linkage between original txn and its reversal (created by reverseTransaction)
```

Per [08-gl-posting-engine.md §10](08-gl-posting-engine.md), every accounting flow funnels through this set of tables.

---

## 6. EOD/BOD artefacts

| Table | Owner | Notes |
|---|---|---|
| `interest_accrual_details` | `interestAccrualCalculation` writer | Keyed `(loan_account_id, accrual_date)`; UPSERTed |
| `penal_interest_accrual_details` | `penalInterestAccrualCalculation` writer | Same pattern, separate table |
| `trial_balance` | `trialBalanceCalculation` | Per-GL daily snapshot |
| `trial_balance_run_history` | TB job | One row per run for re-run / status |
| `loan_account_derived_fields` | `updateLoanAccountDerivedFieldsJob` | Daily refresh |
| `loan_account_derived_fields_monthly` | `updateLoanAccountDerivedFieldsMonthlyJob` | Monthly refresh |

---

## 7. Disbursement mechanics

| Table | Notes |
|---|---|
| `loan_disbursement_transaction` | One row per disbursement attempt (status, request payload, response) |
| `loan_disbursement_charge_details` | Charges netted from disbursement (e.g. processing fee) |
| `loan_disbursement_mode_details` | Mode (NEFT/STP/Manual) + per-mode reference numbers |
| `loan_disbursement_cancellation_*` (multiple) | Maker-checker drafts, child-event linkage, parent reschedule trail |
| `bank_service_call_retry` | One row per pending/failed bank NEFT call. Drained by `accountingBankServiceRetryJob` |
| `disbursement_cancellation_insurance_staging_details` | Inbound insurance file rows for cancellations |

---

## 8. Mandates (eNACH + SI)

eNACH:
- `enach_presentation_details`, `enach_presentation_loan_account_details`, `enach_presentation_file_details` — outbound presentation files (one per cycle)
- `enach_representation_details`, `enach_representation_loan_account_details` — re-presentation files for failed presentations

Standing Instructions (SI / NACH):
- `si_presentation_details`, `si_presentation_file_details`, `si_presentation_loan_account_details` — outbound SI presentation
- `si_lien_presentation_file_details`, `si_auto_hold_presentation_file_details` — lien marking variants
- `si_manual_hold_*` — operator-driven hold marking/removal
- `si_failed_presentation_details` — bounces, drives `accountingBankServiceRetryJob`-style retries

---

## 9. Insurance + death foreclosure

`insurance_product`, `insured_type_calculation_matrix_details`, `insurance_calculation_matrix_slab_details` — premium calculation masters per provider/slab.
`insurance_not_applicable_states` — exclusion list.

Death-foreclosure cluster (one set per claim):
`death_foreclosure_details`, `death_foreclosure_appointee_details`, `death_foreclosure_nominee_details`, `death_foreclosure_payment_mode_details`, `death_foreclosure_details_document`, `death_foreclosure_insurance_staging_details`.

---

## 10. NPA / asset classification

```
asset_classification_master         ← name, code, description (e.g. STD, SMA-0, SMA-1, SMA-2, SUBSTANDARD, DOUBTFUL, LOSS)
asset_classification_slabs          ← bands within a classification

asset_criteria_master               ← named criteria sets (e.g. "MFI rule")
asset_criteria_slabs                ← slabs (DPD ranges) → asset_classification_slabs
asset_criteria_group                ← grouping for sharing across products

loan_product_asset_criteria         ← binds product → asset_criteria_slab + 4 appropriation components + liquidationOrder
                                      (read by RepaymentApproppriationProcessor — see 08 §7)
```

`loan_account.asset_criteria_slabs_id` is the current slab; `past_due_days` decides which slab applies. The recomputation chain inside `runEODJobs`:

`loanAccountDpdCalcJob` → updates `past_due_days`
→ `loanAccountAssetCriteriaJob` → updates `asset_criteria_slabs_id` + `asset_criteria_group_id`
→ `loanAccountAssetClassificationJob` → updates `loan_account_derived_fields.asset_classification`

---

## 11. Quick "where do I look?" lookup

| You're investigating… | Start with table(s) | Joined to |
|---|---|---|
| A specific loan's history | `account` + `loan_account` | every `loan_account_*` child via `account_id` |
| A specific transaction | `transaction_master` | `transaction_partition_details` (legs), `transaction_metadata`, `transaction_details` |
| Why a repayment posted weirdly | `loan_due_details` (sorted by `due_date`, `component_type`) + `loan_account_payments_details` | `loan_product_asset_criteria` for liquidation order |
| Why a disbursement is stuck | `loan_account` (`disbursement_status`, `loan_status`) + `bank_service_call_retry` | `loan_disbursement_transaction` |
| SHG/JLG fan-out stuck | `loan_account_events_queue WHERE parent_account_id=? AND event_status='P'` | `account` (children of parent) |
| Wrong GL on a leg | `transaction_partition_details` for the txn ref → `gl_code` | `product_transaction_catalogue_placeholder` for `(product_id, txn_cat_id, placeholder_code)` |
| EOD interest looks wrong | `interest_accrual_details WHERE loan_account_id=?` | `interest_setup` slabs effective on the accrual date |
| NPA tag looks wrong | `loan_account.past_due_days` + `loan_account.asset_criteria_slabs_id` | `asset_criteria_slabs` for slab boundaries |
| Trial balance off | `trial_balance WHERE business_date=?` | `trial_balance_run_history` for the run id |

---

## 12. Caveats / what's NOT in this model

- **Customer / actor tables live in `mfi_actor`** — not here. `loan_account.customer_id` is an FK across services (resolved via gateway).
- **Approval workflow** lives in `mfi_approval` — drafts, workflow, audit_log_for_approval. The accounting service only sees `application_id` references in its audit_log.
- **Tasks** (operator workflow) live in `mfi_task`. Accounting writes references via `*_createOrUpdateTask` / `*_deleteTask` API calls.
- **Spring Batch meta-tables** (`BATCH_JOB_INSTANCE`, `BATCH_JOB_EXECUTION`, `BATCH_STEP_EXECUTION`, `BATCH_STEP_EXECUTION_CONTEXT`) live in `mfi_accounting` (same datasource), but are managed by Spring Batch and have nothing to do with `mfi_batch.batch_job` (which is the *registry* in the batch service — see [03-batch-dependency.md](03-batch-dependency.md)).
- **Audit trail**: `audit_log` is in `mfi_audit`, not here. Accounting emits via the framework's `<AuditData>` annotation on each Request.
