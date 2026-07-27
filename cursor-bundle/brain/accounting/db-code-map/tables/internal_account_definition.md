# `mfi_accounting.internal_account_definition`

> Master — defines the *templates* (e.g. "Bank Receivable", "Loan Principal", "Interest Income"). Each template gets one `internal_account` row per office.

## Purpose

Logical account types the platform knows about. Bound to GL via `gl_id`. Every `internal_account_definition` has N `internal_account` instances (one per office).

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `code` | Unique business code (e.g. `BANK_RECEIVABLE`) |
| `name`, `description` | |
| `gl_id` | FK → `general_ledger.id` |
| `category`, `bal_type`, `currency` | Inherited semantics |
| `status`, `is_deleted`, audit cols | |

## JPA entity

[`internalaccountdefinition/entity/InternalAccountDefinitionEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/internalaccountdefinition/entity/InternalAccountDefinitionEntity.java)

## DAO

[`internalaccountdefinition/daoservice/InternalAccountDefinitionDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/internalaccountdefinition/daoservice/InternalAccountDefinitionDAOService.java)

## Writers

- `createOrUpdateInternalAccountDefinition` flow

## Readers

- `ExecuteTransactionRulesProcessor.resolveInternalAccountFromPlaceholderThroughProduct` — joined with `product_transaction_catalogue__placeholder__iad` to get `(internal_account_definition_id, gl_code)`
- `ExecuteTransactionRulesProcessor.getInternalAccountEntity` — fetched when `internal_account` is missing for office (for fallback / error context)

## Related Requests

- `postTransaction` — runtime read
- `createOrUpdateInternalAccountDefinition`, `getInternalAccountDefinitionDetails`, `getInternalAccountDefinitionList`

## Common queries

```sql
-- All definitions with their bound GL
SELECT iad.code, iad.name, gl.code AS gl_code, gl.name AS gl_name
  FROM mfi_accounting.internal_account_definition iad
  JOIN mfi_accounting.general_ledger gl ON gl.id = iad.gl_id
 WHERE iad.is_deleted=false ORDER BY iad.code;
```

## Gotchas

1. **Definition is the template; `internal_account` is the per-office instance.** They're 1:N.
2. **Changing `gl_id` on a definition** affects every future posting that resolves to it. Existing partition rows keep the old GL.
