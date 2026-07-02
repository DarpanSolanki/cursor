# `mfi_accounting.transaction_details`

> Per-account ledger row. One row per affected `account_number` in a transaction. Drives `account_balance` updates.

## Purpose

Account-level journal — for each account hit by a transaction, the running ledger is recorded here. Joined with `transaction_master` + `transaction_partition_details` for full statement queries.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `transaction_master_id` | FK → `transaction_master.id` |
| `account_number` | The account hit |
| `cr_dr_indicator` | D / C |
| `amount` | The leg amount (mirrors partition_details) |
| `running_balance` | Account balance after this txn |
| `currency` | |
| `value_date`, `created_on` | |

## JPA entity

`transaction/entity/TransactionDetailsEntity.java`

## Writers

- `CreateTransactionDetailsProcessor` — `postTransaction` REAL mode

## Readers

- `getAccountStatementProcessor`, `getLoanAccountStatementProcessor`
- Reporting service extracts

## Related Requests

- `postTransaction` (writer)
- `getAccountStatement`, `getLoanAccountStatement`

## Common queries

```sql
-- Statement for an account
SELECT td.created_on, td.cr_dr_indicator, td.amount, td.running_balance, tm.transaction_ref_no
  FROM mfi_accounting.transaction_details td
  JOIN mfi_accounting.transaction_master tm ON tm.id = td.transaction_master_id
 WHERE td.account_number = ?
 ORDER BY td.created_on DESC LIMIT 50;
```

## Gotchas

1. **Mirrors `transaction_partition_details`** but at the account-statement granularity (one row per affected account, not per leg-of-leg).
2. **`running_balance` is computed server-side at insertion time** — keeps statement reads cheap.
