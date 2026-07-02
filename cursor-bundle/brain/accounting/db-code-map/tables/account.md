# `mfi_accounting.account`

> Generic account row; specialised by `loan_account` (loans) and `savings_account` (savings) via JOINED inheritance.

## Purpose

Every account-like entity (loan, savings, internal_account) starts as a row here. Holds:
- Account number (the LAN for loans)
- Tenant-scoped office + product-scheme pointers
- Generic status (5-value `AccountStatus`)
- Parent/child wiring for SHG/JLG (`parent_account_id`)

## Schema (live, 19 cols)

| Column | Type | Null? | Meaning |
|---|---|:-:|---|
| `id` | bigint | NOT NULL | PK; shared with child rows in `loan_account.account_id` / `savings_account.account_id` |
| `account_number` | varchar | NOT NULL | The LAN (e.g. `LAN0001234`); externally-visible identifier |
| `type` | varchar | NOT NULL | `AccountType` enum: `LOANS` or `SAVINGS` |
| `currency` | varchar | NOT NULL | ISO code (e.g. INR) |
| `product_scheme_id` | bigint | NOT NULL | FK → `product_scheme.id` |
| `office_id` | bigint | NOT NULL | FK → `mfi_actor.office.id` (logical) |
| `office_code` | varchar | NOT NULL | Denorm of office.code |
| `status` | varchar | NOT NULL | `AccountStatus` enum: ACTIVE / INACTIVE / CLOSED / CANCELLED / APPROVED |
| `opening_date` | timestamp | NOT NULL | When the account was opened |
| `closing_date` | timestamp | NULL | Set when CLOSED (kept even after reopening — historical record) |
| `blocked` | boolean | NULL | If account is on hold |
| `is_deleted` | boolean | NOT NULL DEFAULT false | Soft-delete |
| `parent_account_id` | bigint | NULL | SHG/JLG: parent's `account.id` (NULL on parent itself); the FK that wires children to parent |
| `created_on`, `created_by`, `updated_on`, `updated_by` | timestamp/varchar | various | Standard audit |
| `approved_on`, `approved_by` | timestamp, varchar | NULL | Maker-checker approval audit |

## JPA entity

[`account/common/entity/AccountEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/entity/AccountEntity.java)

- `@Inheritance(strategy = InheritanceType.JOINED)` — base of the inheritance hierarchy
- `@Table(name = "account")`
- Defines two enums: `AccountType` (SAVINGS/LOANS) and `AccountStatus` (5 values)

## DAO + Repository

- [`account/common/repository/AccountDAOService.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/repository/AccountDAOService.java)
- [`account/common/repository/AccountRepository.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/common/repository/AccountRepository.java)

## Writers

| Processor | Action | Triggered by Request | Notes |
|---|---|---|---|
| `CreateLoanAccountProcessor` | INSERT (parent) | `disburseLoan` | creates account+loan_account in one txn |
| `bookChildLoanProcessor` | INSERT (child) | `childLoanDisbursement` (queued via CLB events) | sets `parent_account_id` to parent's `account.id` |
| `UpdateLoanAccountStatusProcessor` | UPDATE `account.status` (via `LOAN_ACCOUNT_ACCOUNT_STATUS_MAP`) | every loan_status change | keeps the two enums in sync |
| Internal-account creation processors | INSERT (type=INTERNAL via internal_account child table) | master CRUDs | |

## Readers

Used everywhere — the LAN is the most-queried key in the system.

- `getOfficeIdFromAccountNumberProcessor` — almost every Request
- `populateAndValidateAccountDetailsProcessor` (in `postTransaction`)
- All `getLoanAccountDetails*` variants
- All foreclosure / repayment / part-prepayment / restructuring readers
- 360-view aggregators

## Related Requests

Almost all of `mfi_orc.xml`, `loans_orc.xml`, `group_mfi_orc.xml`, `product_transaction_orc.xml`. Anything that takes `account_number` as input.

## Related flows

- All flows in [`../../../flows/`](../../../flows/) reference this table

## Common diagnostic queries

```sql
-- Lookup by LAN
SELECT * FROM mfi_accounting.account WHERE account_number = ?;

-- Find all children of a parent SHG/JLG account
SELECT id, account_number, parent_account_id FROM mfi_accounting.account
 WHERE parent_account_id = (SELECT id FROM mfi_accounting.account WHERE account_number = ?);

-- Newest loans created today
SELECT account_number, type, status, created_on FROM mfi_accounting.account
 WHERE type='LOANS' AND created_on >= CURRENT_DATE - INTERVAL '1 day'
 ORDER BY created_on DESC LIMIT 50;
```

## Gotchas

1. **`status` is 5-valued AccountStatus**, NOT 16-valued LoanStatus. Read `loan_account.loan_status` for loan state.
2. **`parent_account_id` is the SHG/JLG wiring** — child accounts have this set; parent has it NULL.
3. **`closing_date` persists after reopening** — re-opened loans don't clear this; intended as historical record.
4. **`account_number` uniqueness scope**: per-tenant unique, not globally.
5. **`type=INTERNAL`** is also possible (internal accounts) — they are accounts too, just for the GL side.
