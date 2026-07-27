# `mfi_accounting.internal_account`

> The physical, office-scoped instance of an `internal_account_definition`. The actual account that gets debited/credited in postings.

## Purpose

Resolution: a placeholder (e.g. `BANK_AC`) → a `internal_account_definition` (e.g. "Bank Receivable") → an `internal_account` instance scoped to a specific `office_id`. The internal_account's `code` is what shows up on `transaction_partition_details.account_number`.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `internal_account_definition_id` | FK → `internal_account_definition.id` |
| `office_id` | FK → `mfi_actor.office.id` (logical) |
| `code` | The actual account code used in postings |
| `currency`, `status`, `created_*`, `updated_*` | |

## JPA entity

[`internalaccount/entity/InternalAccountEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/internalaccount/entity/InternalAccountEntity.java)

## DAO

[`internalaccount/daoservice/InternalAccountDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/internalaccount/daoservice/InternalAccountDAOService.java)

## Writers

- `createOrUpdateInternalAccount` flow

## Readers

- [`ExecuteTransactionRulesProcessor.getInternalAccountEntity`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L300) — falls back to `loan.internal.account.default.office.id` (default `1`) if the office-specific instance isn't found
- Admin UI listings

## Related Requests

- `postTransaction` — runtime read
- `createOrUpdateInternalAccount`, `getInternalAccountList`, `getInternalAccountDetails`

## Related flows

- [GL posting engine §3 phase 1](../../08-gl-posting-engine.md#3-executetransactionrulesprocessor--the-engine-itself)

## Common queries

```sql
-- All internal accounts for an office
SELECT ia.id, iad.code AS def_code, ia.code AS account_code, ia.currency, ia.status
  FROM mfi_accounting.internal_account ia
  JOIN mfi_accounting.internal_account_definition iad ON iad.id = ia.internal_account_definition_id
 WHERE ia.office_id = ?
 ORDER BY iad.code;

-- Detect missing per-office instances (engine throws 134182 if missing)
SELECT iad.code, iad.id AS def_id,
       (SELECT COUNT(*) FROM mfi_accounting.internal_account ia WHERE ia.internal_account_definition_id = iad.id) AS instance_count
  FROM mfi_accounting.internal_account_definition iad
 ORDER BY instance_count;
```

## Gotchas

1. **Engine error `134182`** = no internal_account exists for `(office_id, internal_account_definition_id)` and no default-office override either. Fix: insert the missing row.
2. **Default office fallback** — if `loan.internal.account.default.office.id` config (default `1`) has the instance, the engine uses that even if the requested office's instance is missing.
3. **`code` is what shows up in postings** — `transaction_partition_details.account_number` matches this.
