# `mfi_accounting.general_ledger`

> The chart of accounts. Every GL hit references one row's `code`. Tagged onto `transaction_partition_details.gl_code`. The base for `trial_balance` aggregation.

## Purpose

Master GL chart. Each row defines one ledger account: code, name, category (asset/liability/income/expense), allowed transaction type, status, etc.

## Schema (live, 17 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `code` | The GL code (e.g. `230101`) — the public identifier |
| `name`, `description` | Human-readable |
| `category` | ASSET / LIABILITY / INCOME / EXPENSE |
| `bal_type` | DEBIT / CREDIT |
| `allowed_transaction_type` | DEBIT / CREDIT / BOTH |
| `currency` | |
| `parent_gl_id` | optional FK for hierarchy |
| `external_reference_number` | optional cross-ref |
| `status`, `is_deleted` | active flag |
| `approved_*`, `created_*`, `updated_*` | audit |

## JPA entity

[`generalledger/entity/GeneralLedgerEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/generalledger/entity/GeneralLedgerEntity.java)

## DAO

[`generalledger/daoservice/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/generalledger/daoservice/)

## Writers

- `createGeneralLedgerProcessor` — `createOrUpdateGeneralLedger` (maker submit, then APPROVE branch persists)
- `updateGeneralLedgerProcessor` — UPDATE
- `deleteGeneralLedgerProcessor` — soft DELETE
- (For savings products: also `CreateSavingsProductGeneralLedgerProcessor` / `UpdateSavingsProductGeneralLedgerProcessor`)

## Readers

- `internal_account_definition` joins → posting engine
- `getGeneralLedgerDetails`, `getGeneralLedgerList` — admin UI
- `trialBalanceCalculation` — TB aggregation by `gl_code`
- Reporting service extracts (RBI ADF GL details)

## Related Requests

- `createOrUpdateGeneralLedger`, `deleteGeneralLedger`, `getGeneralLedgerDetails`, `getGeneralLedgerList`
- `getGeneralLedgerListBasedOnHierarchy`
- `trialBalanceCalculation` (read), `generateTBZeroisationReport`

## Related flows

- [GL posting engine](../../08-gl-posting-engine.md)
- [Money flow](../../../system/04-money-flow-rupee-journey.md)
- [TB imbalance runbook](../../../runbooks/trial-balance-imbalance.md)

## Common queries

```sql
-- All GLs by category
SELECT category, COUNT(*) FROM mfi_accounting.general_ledger
 WHERE is_deleted=false GROUP BY 1 ORDER BY 1;

-- Find GL by code
SELECT id, code, name, category, bal_type, status
  FROM mfi_accounting.general_ledger WHERE code = ?;

-- GLs without any internal_account binding (orphans)
SELECT gl.code, gl.name FROM mfi_accounting.general_ledger gl
 LEFT JOIN mfi_accounting.internal_account_definition iad ON iad.gl_id = gl.id
 WHERE iad.id IS NULL AND gl.is_deleted=false LIMIT 50;
```

## Gotchas

1. **`code` is the public identifier** in postings — `transaction_partition_details.gl_code` matches this.
2. **`bal_type` vs `allowed_transaction_type`** — the former is the natural balance side (asset/expense = DEBIT, liability/income = CREDIT). The latter restricts what the rules can post.
3. **For child loans, the GL is a row in `child_general_ledger`** with `code = "CG" + parent_gl.code`. See [child_general_ledger.md](child_general_ledger.md).
4. **Soft-delete only** — `is_deleted=true` rows still exist; readers must filter.
