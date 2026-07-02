# `mfi_accounting.transaction_catalogue`

> Master — names every transaction the platform can post. e.g. `LOAN_DISB_PRIN`, `LOAN_REP_INT`, `PENAL_INT_BOOK`. Every `postTransaction` call references one row here via `transaction_catalogue_id`.

## Purpose

Catalogue of named transactions. Each is bound to a list of rules (`transaction_accounting_rule`) that define its legs.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `code` | Unique business code (e.g. `LOAN_REPAYMENT`) |
| `name`, `description` | Human-readable |
| `product_type` | Which product type it applies to |
| `transaction_type`, `transaction_sub_type` | Categorisation |
| `currency` | |
| `created_*`, `updated_*` | Audit |

## JPA entity

[`transaction/entity/TransactionCatalogueEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/entity/TransactionCatalogueEntity.java)

## DAO

[`transaction/repository/TransactionCatalogueDAOService.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/repository/TransactionCatalogueDAOService.java)

## Writers

| Processor | Triggered by |
|---|---|
| `createOrUpdateTransactionCatalogue` flow | `createOrUpdateTransactionCatalogue` Request |
| `deleteTransactionCatalogue` flow | `deleteTransactionCatalogue` |

## Readers

- [`GetTransactionCatalogueIdProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/GetTransactionCatalogueIdProcessor.java) — resolves `code` → `id` at the start of `postTransaction`
- [`GetTransactionCatalogueListProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/GetTransactionCatalogueListProcessor.java) — admin UI listings
- [`GetTransactionCatalogueListGroupedByProductTypeProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/GetTransactionCatalogueListGroupedByProductTypeProcessor.java) — grouped views

## Related Requests

- `postTransaction` — primary reader
- `createOrUpdateTransactionCatalogue`, `deleteTransactionCatalogue` — admin
- `getTransactionCatalogueList*` — UI
- `getProductTransactionCatalogueList`

## Related flows

- [GL posting engine](../../08-gl-posting-engine.md) — how a catalogue resolves to legs

## Common queries

```sql
-- All catalogues
SELECT id, code, name, product_type FROM mfi_accounting.transaction_catalogue ORDER BY code;

-- Catalogues for loans
SELECT code, name FROM mfi_accounting.transaction_catalogue
 WHERE product_type = 'LOANS' ORDER BY code;
```

## Gotchas

1. **`code` is the public identifier** — all callers reference by code, not id. Renaming a code is a breaking change.
2. **Linked to `transaction_accounting_rule`** by id — adding a new code requires also adding rule rows for it (see that table's doc).
3. **Hot read during `postTransaction`** — cached in accounting Redis (DB 5).
