# `mfi_accounting.placeholder_master`

> Master — **symbolic account names** used in `transaction_accounting_rule`. Resolved at runtime to a real `internal_account` (or actor account) by `ExecuteTransactionRulesProcessor`.

## Purpose

Decouples accounting rule definitions from physical accounts. A rule says "credit `LOAN_PRINCIPAL_AC`"; the placeholder master + `product_transaction_catalogue__placeholder__iad` resolves that to "internal_account_definition X for office Y → internal_account Z → GL code 230101".

## Schema

| Column | Meaning |
|---|---|
| `id` | PK |
| `code` | The placeholder name (e.g. `LOAN_PRINCIPAL_AC`, `BANK_AC`, `CUSTOMER_AC`) |
| `name`, `description` | Human-readable |
| `is_actor_account` | Boolean — if true, account number comes from EC at runtime (the customer's account); not from product binding |
| `is_externally_passed_account` | Boolean — account number is supplied externally in the request payload |
| `created_*`, `updated_*` | Audit |

## JPA entity

[`placeholdermaster/entity/PlaceholderMasterEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/placeholdermaster/entity/PlaceholderMasterEntity.java)

## DAO

[`placeholdermaster/dao/PlaceholderMasterDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/placeholdermaster/dao/PlaceholderMasterDAOService.java)

## Writers

- `createOrUpdatePlaceholderMaster` flow (admin)
- `deletePlaceholderMaster`
- `createOrUpdatePlaceholderMasterListForProductType` (bulk)

## Readers

- [`ExecuteTransactionRulesProcessor.resolvePlaceholder`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L233) — runtime, the heavy reader
- Admin UI listings via `getPlaceholderMaster*` Requests

## Related Requests

- `postTransaction` — runtime read (hot path)
- `createOrUpdatePlaceholderMaster`, `deletePlaceholderMaster`
- `createOrUpdatePlaceholderMasterListForProductType`

## Related flows

- [GL posting engine §1](../../08-gl-posting-engine.md#1-the-five-masters-that-drive-every-gl-hit)

## Common queries

```sql
-- All placeholders
SELECT code, name, is_actor_account, is_externally_passed_account
  FROM mfi_accounting.placeholder_master ORDER BY code;

-- Find which catalogues use a placeholder (impact analysis)
SELECT DISTINCT tc.code AS catalogue
  FROM mfi_accounting.transaction_accounting_rule tar
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
  JOIN mfi_accounting.placeholder_master pm
    ON pm.code IN (tar.debit_account_placeholder, tar.credit_account_placeholder, tar.fallback_credit_placeholder)
 WHERE pm.code = ?;
```

## Gotchas

1. **`is_actor_account=true`** changes resolution at runtime — placeholder value comes from EC key matching `placeholder.code`, NOT from product binding. Used for customer/borrower accounts.
2. **`is_externally_passed_account=true`** — account number is read from the EC key matching `placeholder.code` (caller passes it). Used for STP/manual-bank scenarios.
3. **Otherwise, default product binding** — looked up via `product_transaction_catalogue__placeholder__iad` for `(product_id, transaction_catalogue_id, placeholder_code)` → `internal_account_definition_id` + `gl_code`. Engine error `134207` if no binding exists.
4. **Hot read during postTransaction** — cached in accounting Redis (DB 5).
