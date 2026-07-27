# `mfi_accounting.loan_account`

> The single most important table in LMS. **80 columns** (entity declares ~30; rest were added by migrations for SHG/JLG, sec-NPA, denormalisation, etc.). Inherits from `account` via JOINED inheritance — the row in `account` shares the same `id` as `loan_account.account_id`.

## Purpose

One row per loan account. Holds:
- The contractual terms (`approved_amount`, `term`, `repayment_frequency`, `maturity_date`, …)
- The current state (`loan_status`, `disbursement_status`, `past_due_days`, `npa_*`)
- Amount denormalisations (`outstanding`, `excess_amount`, `interest_suspense_amount`)
- Asset-criteria classification pointers (`asset_criteria_group_id`, `asset_criteria_slabs_id`, `asset_classification_slabs_id`)
- SHG/JLG parent/child wiring (`parent_loan_account_id`, `fraction`, `has_child_accounts`)
- Sec-NPA fields (`is_sec_npa`, `sec_npa_*`)
- 11 generic `filler_*` columns for tenant-specific extensions
- 8 `la_*` columns denormalised from parent `account` row (Yugabyte LSM optimization — avoids joins)

## Schema (live from mfi_qa3, 80 cols)

Key columns grouped by concern. Re-fetch full schema with `tools/inspect-table.sh loan_account`.

### Identity / FKs
| Column | Type | Meaning |
|---|---|---|
| `account_id` | bigint NOT NULL | PK; FK → `account.id` (JOINED inheritance) |
| `loan_product_id` | bigint NOT NULL | FK → `loan_product.id` |
| `customer_id` | bigint NOT NULL | FK → `mfi_actor.customer.id` (logical, not enforced) |
| `external_ref_number` | varchar NOT NULL | LOS-side ref; used for Kafka dedup (`disburseLoan{productId}_{externalRefNumber}`) |
| `parent_loan_account_id` | bigint NULL | SHG/JLG: parent's loan_account.account_id (NULL on parent itself) |
| `fraction` | numeric NULL | SHG/JLG child's share of parent EMI (sum of children's fractions = 1.0) |
| `has_child_accounts` | boolean NOT NULL DEFAULT false | true on SHG/JLG parent row |

### Contract terms
| Column | Type | Meaning |
|---|---|---|
| `approved_amount`, `loan_amount`, `disbursed_amount`, `requested_loan_amount`, `cross_sell_amount` | numeric | Various amount snapshots; `disbursed_amount` may differ from `loan_amount` if charges deducted up-front |
| `term`, `term_unit` | int, varchar | Loan tenure (e.g. 24 MONTH) |
| `number_of_installments` | int NOT NULL | Total installments |
| `repayment_frequency`, `interest_frequency` | varchar | DAILY/WEEKLY/FORTNIGHTLY/MONTHLY/YEARLY |
| `interest_calculation_basis` | varchar NOT NULL DEFAULT 'REDUCING_BALANCE' | flat / reducing / etc. |
| `expected_disbursement_date`, `actual_first_repayment_date`, `first_repayment_date`, `first_interest_payment_date`, `maturity_date`, `sanction_date` | timestamp | Lifecycle dates |
| `purpose` | varchar | Loan purpose code |

### State machine — read these together
| Column | Type | Meaning |
|---|---|---|
| `loan_status` | varchar NOT NULL | One of 16 `LoanStatus` enum values (see `07-loan-account-lifecycle.md`) |
| `disbursement_status` | varchar NOT NULL | Bank-side state machine: BANK_SUCCESS / LOAN_BOOKED / NEFT_STAGE_* / PARENT_SUCCESS / COMPLETED / etc. |
| `cancelled_on` | timestamp NULL | Set when DISB_CNCL |
| `approved_on`, `approved_by` | timestamp, varchar | Maker-checker approval audit |
| `created_on`, `created_by`, `updated_on`, `updated_by` | timestamp, varchar | Standard audit |
| `is_deleted` | boolean NOT NULL DEFAULT false | Soft-delete flag |

### DPD / NPA classification
| Column | Type | Meaning |
|---|---|---|
| `past_due_days` | bigint NOT NULL | Refreshed daily by `loanAccountDpdCalcJob` |
| `asset_criteria_group_id`, `asset_criteria_slabs_id` | bigint NOT NULL | Current criteria slab. Refreshed by `loanAccountAssetCriteriaJob` |
| `asset_classification_slabs_id` | bigint NOT NULL | Final asset classification (STD/SMA-0/1/2/Substandard/etc.). Refreshed by `loanAccountAssetClassificationJob` |
| `npa_ageing_start_date`, `npa_ageing_days`, `npa_tagging_date` | timestamp/bigint/timestamp NULL | Set when loan crosses NPA threshold; non-null = NPA |
| `interest_suspense_amount` | numeric NULL | When NPA, interest is shunted here instead of credited to interest income |
| `is_sec_npa`, `sec_npa_*` (5 cols) | various | Secondary-NPA tracking (RBI vendor reverse-feed) |
| `delinq_string` | varchar NULL | Delinquency bucket history string |

### Amount denormalisations
| Column | Type | Meaning |
|---|---|---|
| `overdue_amount` | numeric NOT NULL | Sum of unpaid components past due |
| `excess_amount` | numeric NULL | Amount paid over due, carried forward for future EMI auto-clear |
| `excess_interest_amount` | numeric NULL | Sub-portion of excess that's pure interest |
| `broken_period_interest_amount` | numeric NULL | Interest for partial-period at start (BPI) |

### NOC + net-off + refund
| Column | Type | Meaning |
|---|---|---|
| `noc_document_id` | int NULL | FK → `document.id` for issued NOC |
| `net_off_account`, `net_off_amount`, `is_external_net_off_acnt` | various | Net-off mechanism |
| `refund_allowed`, `refund_remarks` | boolean, varchar | Refund eligibility |
| `enach_bounce_count` | int NULL | Cumulative bounce count |

### Denormalised from `account` (Yugabyte query optimisation — added later)
| Column | Type | Source |
|---|---|---|
| `la_account_number` | varchar | `account.account_number` |
| `la_office_id`, `la_office_code` | bigint, varchar | `account.office_id`, `office_code` |
| `la_product_scheme_id` | bigint | `account.product_scheme_id` |
| `la_currency` | varchar | `account.currency` |
| `la_opening_date`, `la_closing_date` | timestamp | `account.opening_date`, `closing_date` |

> **Why the duplication:** Yugabyte's LSM-tree storage makes JOINs across tablets expensive. Common reads on `loan_account` need `account_number`/`office_id`; denormalising avoids the join. **Writers must keep them in sync** with the parent `account` row.

### Tenant-specific extension fillers
`filler_1` … `filler_11` (mixed types — varchar, date, numeric, boolean) — for per-tenant custom fields without schema migrations.

### `sourcing_emp_id`, `servicing_emp_id`
Track which actor/employee originated and currently services the loan.

## Key indexes (live)

- `loan_account_pkey` on `account_id` (PK)
- `loan_account_account_id_idx` (redundant but cached)
- Several others — run `inspect-table.sh loan_account` for full list

## JPA entity

[`account/loans/entity/LoanAccountEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEntity.java)

Notes:
- `@PrimaryKeyJoinColumn(name = "account_id")` — JOINED inheritance from `AccountEntity`
- `@Table(name = "loan_account")`
- Defines two enums on the entity itself: `LoanStatus` (16 values) and `InactiveLoanStatus` (subset used by guard checks)
- Static `DISBURSEMENT_BLOCK_STATUSES` list — disbursement_status values that block re-disbursement attempts

## DAO + Repository

- [`account/loans/repository/LoanAccountDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/repository/LoanAccountDAOService.java)
- [`account/loans/repository/LoanAccountRepository.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/repository/LoanAccountRepository.java)

## Writers

| Processor | Action | Triggered by Request | Notes |
|---|---|---|---|
| [`CreateLoanAccountProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/loans/processor/CreateLoanAccountProcessor.java) | INSERT | `disburseLoan` (mfi_orc.xml:4, function_sub_code DEFAULT/LAN_CREATED) | initial `loan_status=APPROVED`, `disbursement_status=LAN_CREATED` |
| `UpdateLoanAccountStatusProcessor` | UPDATE `loan_status` (+ syncs `account.status` via `LOAN_ACCOUNT_ACCOUNT_STATUS_MAP`) | almost every state-change Request: `disburseLoan`, `loanForeclosure`, `loanPrepayment`, `loanAccountClosure`, `*Reopening`, `*Restructuring`, `*Rebooking`, `*PartPrepayment`, `*DisbursementCancellation`, `loanWriteoff` | The single point through which loan_status changes |
| `loanAccountDpdCalcProcessor` | UPDATE `past_due_days` | EOD `loanAccountDpdCalcJob`; inline in `loanRepayment`, foreclosure | uses calendar + due_details |
| `loanAccountAssetCriteriaProcessor` | UPDATE `asset_criteria_group_id`, `asset_criteria_slabs_id` | EOD; inline in repayment/foreclosure | walks `loan_product_asset_criteria` |
| `loanAccountAssetClassificationProcessor` | UPDATE `asset_classification_slabs_id`, `npa_*` | EOD; inline | sets/clears NPA flags |
| `populateLoanAutoClosureReqProcessor` + `loanAccountAutoClosureProcessor` | UPDATE `loan_status=CLOSED`, `cancelled_on` | inline in `loanRepayment`, `childLoanRepayment`, foreclosure when fully paid | |
| `pushLoanAccountClosureDetailsProcessor` | UPDATE final close-state | `loanForeclosure`, foreclosure flows | |
| `updateLoanAccountForExcessAmountProcessor` | UPDATE `excess_amount`, `excess_interest_amount` | `loanRepayment` | after appropriation leaves residue |
| `updateLoanAccountChildAccountEntityProcessor` | UPDATE child rows on parent | `childLoanAccountExcessAmountRefund`, others | |
| Sec-NPA writer (`bulkSGToSecNpaReverseFeedFileJob`) | UPDATE `is_sec_npa`, `sec_npa_*` | scheduled batch | from RBI vendor file |
| `LmsMessageBrokerConsumer` itself doesn't write, but invokes the chain | | `disburseLoan` Kafka path | |

## Readers

Heavy. The most-frequent:

| Processor | Triggered by Request | Purpose |
|---|---|---|
| `GetLoanAccountDetailsProcessor` | `getLoanAccountDetails`, plus inline calls in many flows | API response |
| `disburseLoan_getLoanAccountDetails` | `disburseLoan` (self-lookup) | check current state |
| `valdiateLoanAccountNumberAndStatusProcessor` | foreclosure, repayment | guard against `InactiveLoanStatus` |
| `getOfficeIdFromAccountNumberProcessor` | every flow that needs the office | reads `la_office_id` (denorm) |
| EOD batch readers | `interestAccrualCalculation`, `loanAccountBillingJob`, `*DpdCalcJob`, etc. | bulk over active loans |
| `LmsMessageBrokerConsumer.getDisburseSkipReason` | `disburseLoan` Kafka path | check ALREADY_ACTIVE / LOCK |

## Related Requests

Almost every Request in `loans_orc.xml`, `mfi_orc.xml`, `group_mfi_orc.xml`. Selected:

- `disburseLoan` (mfi_orc.xml:4) — primary writer
- `getLoanAccountDetails`, `getLoanAccountList`, `getLoanAccountOverview`, `getLoanAccountSummary`, `getLoanAccountBasic`
- `loanRepayment` (mfi_orc.xml:2661), `childLoanRepayment`
- `loanForeclosure`, `loanPrepayment`, `childLoanForeclosure`, `individualChildLoanForeclosure`
- `loanAccountPartPrepayment`, `parentLoanAccountPartPrepayment`, `childLoanPartPrepayment`
- `LoanAccountRestructuring`, `loanAccountReopening`, `loanAccountRebooking` (and child variants)
- `loanWriteoff`, `loanAccountClosure`, `loanAccountAutoClosure`
- `loanDisbursementCancellation`, `childLoanDisbursementCancellation`
- `loanAccountDpdCalcJob`, `loanAccountAssetCriteriaJob`, `loanAccountAssetClassificationJob`
- `updateLoanAccountDerivedFieldsJob` (reads to populate `loan_account_derived_fields`)
- `loanAccountTransactionReversal`, `childLoanTransactionReversal`
- `loanAccountExcessAmountRefund`, `childLoanAccountExcessAmountRefund`

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)
- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)
- [SHG/JLG group loan](../../../flows/shg-jlg-group-loan.md)
- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md)
- [NPA & provisioning](../../../flows/npa-and-provisioning.md)
- [Lifecycle state machine](../../07-loan-account-lifecycle.md)

## Common diagnostic queries

```sql
-- State of a single loan
SELECT a.account_number, la.loan_status, la.disbursement_status,
       la.past_due_days, la.npa_ageing_start_date, la.parent_loan_account_id, la.fraction
  FROM mfi_accounting.loan_account la
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE a.account_number = ? OR la.external_ref_number = ?;

-- All children of a parent
SELECT child.account_number, child.fraction, child.loan_status
  FROM mfi_accounting.loan_account child
  JOIN mfi_accounting.account ca ON ca.id = child.account_id
 WHERE ca.parent_account_id = (SELECT id FROM mfi_accounting.account WHERE account_number = ?);

-- Loans stuck mid-disbursement
SELECT external_ref_number, loan_status, disbursement_status, updated_on
  FROM mfi_accounting.loan_account
 WHERE loan_status = 'APPROVED' AND disbursement_status NOT IN ('COMPLETED','PARENT_SUCCESS')
   AND updated_on < NOW() - INTERVAL '1 hour'
 ORDER BY updated_on;
```

## Gotchas

1. **Two state columns** — `loan_status` (16 values) AND `disbursement_status` (8+ values). They are NOT the same. Always read both.
2. **`account.status` (5 values) is NOT loan_status.** It's the generic 5-value AccountStatus. Always read `loan_account.loan_status` for loan state.
3. **Denormalised `la_*` columns** — must be kept in sync with `account` row by writers. A bug that updates `account.office_id` without updating `loan_account.la_office_id` causes split-brain.
4. **`fraction` is NULL on parent**, set on children (sum of children's fractions = 1.0).
5. **`has_child_accounts`** is the cheap way to detect SHG/JLG parents in queries (no need to LEFT JOIN children).
6. **80 columns, but only ~30 are mapped on the entity.** Newer columns added via Flyway migrations are read/written via DAO+native SQL or via the entity's getter/setter generated reflectively.
7. **Sec-NPA fields populated only by RBI reverse-feed** — most loans have these as NULL.
8. **NPA columns**: `npa_ageing_start_date != NULL` is the canonical "this loan is in NPA right now" check.
