# `mfi_accounting.account_balance`

> Per-account current-balance row. Updated transactionally as part of `postTransaction` flow.

## Schema (live, 5 cols)

| Column | Meaning |
|---|---|
| `account_id` (PK) | FK → `account.id` |
| `available_balance` | Current usable balance |
| `total_balance` | Including holds |
| `currency` | |
| `updated_on` | |

## JPA entity

[`account/balance/entity/AccountBalanceEntity.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/account/balance/entity/AccountBalanceEntity.java)

## DAO + Repository

[`account/balance/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/balance/)

## Writers

- Inside `postTransaction` REAL-mode chain — balance updates happen alongside `transaction_details` writes
- (commented-out: `validateAndUpdateInternalAccountBalanceProcessor` was the explicit gate; current code does it inside `createTransactionDetailsProcessor` per the orchestration in product_transaction_orc.xml:21-30)

## Readers

- `getAccountBalancesProcessor` — `getAccountBalances` Request
- `populateAndValidateActorAccountBalanceProcessor` (TRIAL mode pre-flight)

## Related Requests

- `postTransaction` — writer (REAL mode)
- `getAccountBalances` — reader

## Common queries

```sql
-- Current balance for an account
SELECT ab.account_id, a.account_number, ab.available_balance, ab.total_balance, ab.currency
  FROM mfi_accounting.account_balance ab
  JOIN mfi_accounting.account a ON a.id = ab.account_id
 WHERE a.account_number = ?;
```

## Gotchas

1. **One row per account_id** — created on first hit, updated thereafter.
2. **Updated atomically with transaction_details inserts** in REAL postings.
3. **Locking**: row-level lock on the account_id during posting prevents concurrent over-spend.
