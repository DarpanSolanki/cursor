# `mfi_accounting.transaction_partition_details`

> The DR/CR legs of every transaction. **2 rows per accounting rule** (DR + CR). For a complex repayment, one txn can have 8+ rows here.

## Purpose

Records the GL-level legs of every `postTransaction` call. Each row represents one leg (one account, one amount, one DR/CR direction). Built by `ExecuteTransactionRulesProcessor`'s output, persisted by `CreateTransactionPartitionDetailsProcessor`.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `transaction_master_id` | FK → `transaction_master.id` |
| `account_number` | The account hit (internal_account.code, or actor account number) |
| `gl_code` | The GL hit. Prefixed with `CG` for child loan transactions (`is_child_account=true`) |
| `cr_dr_indicator` | `D` (debit) or `C` (credit) |
| `amount` | The leg amount |
| `source_amount` | Original input amount (before pricing/tax) |
| `currency` | Leg currency |
| `narration` | Templated narration (placeholder-substituted) |
| `part_info_1`, `part_info_2`, `part_info_3` | Free-form per-leg metadata (placeholder-substituted) |
| `reference_code`, `reference_description`, `display_flag` | From the rule definition |
| `office_id` | Posting office |
| `entity_id`, `entity_type` | The originating entity (e.g. `loan_account_id`, `LOANS`) |
| `child_gl_code` | boolean — true if `gl_code` got the `CG` prefix |

## JPA entity

[`transaction/entity/TransactionPartitionDetailsEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/entity/TransactionPartitionDetailsEntity.java)

## Writers

| Processor | Action | Triggered by |
|---|---|---|
| `CreateTransactionPartitionDetailsProcessor` | INSERT (one per leg) | `postTransaction` REAL mode |
| (output of) [`ExecuteTransactionRulesProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java) | builds the rows in-memory; persistor saves them | (same Request) |
| `ReverseTransactionProcessor` | INSERT (mirror legs with flipped cr_dr_indicator) | `reverseTransaction` |

## Readers

- `getTransactionPartitionDetailsProcessor` — surface to API
- `getAccountStatementProcessor` / `getLoanAccountStatementProcessor` — joined into statement
- TB calculation — aggregated for daily snapshot
- Reporting service extracts (RBI ADF, GL details)

## Related Requests

- `postTransaction` (writer; called by virtually every state-changing flow)
- `reverseTransaction`
- `getTransactionPartitionDetails`
- `getAccountStatement`, `getLoanAccountStatement`
- `trialBalanceCalculation` (reads to build TB)

## Related flows

- [GL posting engine](../../08-gl-posting-engine.md) — explains how rows are derived
- [Money flow — rupee journey](../../../system/04-money-flow-rupee-journey.md)
- [Trial balance imbalance runbook](../../../runbooks/trial-balance-imbalance.md)

## Common queries

```sql
-- Legs of one transaction (DR + CR pairs should sum to zero per gl_code)
SELECT cr_dr_indicator, account_number, gl_code, amount, narration
  FROM mfi_accounting.transaction_partition_details
  JOIN mfi_accounting.transaction_master tm ON tm.id = transaction_master_id
 WHERE tm.transaction_ref_no = ?
 ORDER BY id;

-- Find asymmetric (broken) transactions on a date
SELECT tm.transaction_ref_no,
       SUM(CASE WHEN tpd.cr_dr_indicator='D' THEN tpd.amount ELSE -tpd.amount END) AS net
  FROM mfi_accounting.transaction_master tm
  JOIN mfi_accounting.transaction_partition_details tpd ON tpd.transaction_master_id = tm.id
 WHERE tm.created_on::date = ?
 GROUP BY tm.transaction_ref_no
HAVING SUM(CASE WHEN tpd.cr_dr_indicator='D' THEN tpd.amount ELSE -tpd.amount END) <> 0;

-- All txns hitting one GL on a date
SELECT tm.transaction_ref_no, tpd.cr_dr_indicator, tpd.amount, tpd.account_number
  FROM mfi_accounting.transaction_partition_details tpd
  JOIN mfi_accounting.transaction_master tm ON tm.id = tpd.transaction_master_id
 WHERE tpd.gl_code = ? AND tm.created_on::date = ?
 ORDER BY tm.created_on;
```

## Gotchas

1. **Sum of DR == sum of CR per txn** (the engine enforces). If not, posting is broken — see [trial-balance-imbalance runbook](../../../runbooks/trial-balance-imbalance.md).
2. **`gl_code` prefix `CG`** for child-loan txns — `ExecuteTransactionRulesProcessor.createPartitionDetails` lines 391-393 prepends if `is_child_account=true`.
3. **Rules with `calculatedAmount=0` are skipped** — leg won't appear in `transaction_partition_details`. This is the most common cause of asymmetric postings.
4. **`entity_id`/`entity_type`** lets you filter "all postings for this loan" without joining to `transaction_metadata`.
5. **`reference_code`** distinguishes legs of the same txn (e.g. `REP_PRIN`, `REP_INT`, `REP_PINT`, `REP_FEE` for a multi-component repayment).
