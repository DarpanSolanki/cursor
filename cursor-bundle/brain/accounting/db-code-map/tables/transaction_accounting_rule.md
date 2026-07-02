# `mfi_accounting.transaction_accounting_rule`

> Master table — defines the legs of a transaction catalogue. **N rows per `transaction_catalogue`** (one per leg). Read by `ExecuteTransactionRulesProcessor` to derive the GL hits.

## Purpose

For every named transaction (e.g. `LOAN_REPAYMENT`), this table defines the legs:
- Source amount (which EC key holds it)
- Debit account placeholder
- Credit account placeholder (+ optional fallback)
- Entry type (`TRANSFER`, `PRICE`, `TAX`)
- Condition expression (SpEL — e.g. `${principal_amount} > 0`)
- Narration template
- Per-leg part-info templates

This is master data — populated at tenant onboarding, modified rarely (CRUD'd via `createOrUpdateAccountingRules`).

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` | PK |
| `transaction_catalogue_id` | FK → `transaction_catalogue.id` |
| `sequence_number` | Ordering — rules execute in this order, intermediate results reused |
| `entry_type` | `TRANSFER` (no compute), `PRICE` (calls priceEngine), `TAX` (calls taxEngine) |
| `entry_sub_type` | e.g. `GST` for tax legs |
| `entry_lookup_code` | Used by tax/price engine to pick slab |
| `reference_code`, `reference_description`, `display_flag` | Per-leg identification |
| `source_amount` | EC key that holds the input amount (e.g. `principal_amount`) |
| `product_resolution_placeholder` | Which placeholder identifies the product context |
| `debit_account_placeholder` | FK → `placeholder_master.code` for the debit side |
| `debit_narration` | Templated string |
| `debit_part_info_1`/`_2`/`_3` | Templated per-leg metadata |
| `credit_account_placeholder` | FK → `placeholder_master.code` for credit side |
| `credit_narration` | Templated |
| `credit_part_info_1`/`_2`/`_3` | Templated |
| `fallback_credit_placeholder`, `fallback_credit_narration`, `fallback_credit_part_info_*` | Fallback credit (e.g. for write-off → suspense) |
| `condition_type` | `ARITHMETIC_CONDITION` (evaluate `condition_expression`) or null (read source key directly) |
| `condition_expression` | SpEL expression evaluated against EC |
| `created_on`, `created_by`, `updated_on`, `updated_by` | Audit |

## JPA entity

[`accountingrules/entity/TransactionAccountingRuleEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/entity/TransactionAccountingRuleEntity.java)

## DAO

[`accountingrules/repository/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/repository/)

## Writers

| Processor | Action | Triggered by Request |
|---|---|---|
| [`CreateAccountingRulesProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/processor/CreateAccountingRulesProcessor.java) | INSERT | `createOrUpdateAccountingRules` (maker submit) |
| [`ModifyTransactionAccountingRuleProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/processor/ModifyTransactionAccountingRuleProcessor.java) | UPDATE | `createOrUpdateAccountingRules` (checker approve / re-edit) |
| [`DeleteTransactionAccountingRuleProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/processor/DeleteTransactionAccountingRuleProcessor.java) | DELETE | `deleteAccountingRules` |

## Readers

THE big one:

| Reader | Triggered by |
|---|---|
| `getTransactionRuleListProcessor` | `postTransaction` — loads the rules into EC `transaction_rule_list` |
| [`ExecuteTransactionRulesProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java) | `postTransaction` — iterates the rule list |
| [`GetTransactionAccountingRuleListProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/processor/GetTransactionAccountingRuleListProcessor.java) | `getTransactionAccountingRuleList` (admin UI) |
| [`PopulateTransactionAccountingRuleByProductTypeProcessor`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/processor/PopulateTransactionAccountingRuleByProductTypeProcessor.java) | various preview Requests |

## Related Requests

- `createOrUpdateAccountingRules`, `deleteAccountingRules`, `classifyTransactionAccountingRuleList` — admin
- `postTransaction` — runtime read (the heavy one)
- `getTransactionAccountingRulesListByIds`, `getTransactionAccountingRuleGroupByProductType` — UI

## Related flows

- [GL posting engine](../../08-gl-posting-engine.md) — explains how rules are interpreted
- [Money flow — rupee journey](../../../system/04-money-flow-rupee-journey.md)

## Common queries

```sql
-- All rules for a catalogue
SELECT sequence_number, entry_type, source_amount,
       debit_account_placeholder, credit_account_placeholder, fallback_credit_placeholder,
       condition_type, condition_expression
  FROM mfi_accounting.transaction_accounting_rule
 WHERE transaction_catalogue_id = (SELECT id FROM mfi_accounting.transaction_catalogue WHERE code = ?)
 ORDER BY sequence_number;

-- Find rules using a specific placeholder (impact analysis if you change placeholder)
SELECT tc.code AS catalogue, tar.sequence_number, tar.debit_account_placeholder, tar.credit_account_placeholder
  FROM mfi_accounting.transaction_accounting_rule tar
  JOIN mfi_accounting.transaction_catalogue tc ON tc.id = tar.transaction_catalogue_id
 WHERE tar.debit_account_placeholder = ? OR tar.credit_account_placeholder = ?;
```

## Gotchas

1. **Rules execute in `sequence_number` order**, and intermediate `reference_code` values are stored in EC for later rules to reference (`condition_expression` like `${REP_PRIN}` references an earlier leg's calculated amount).
2. **`entry_type` decides the engine** — `TRANSFER` does no compute (`calculatedAmount = sourceAmount`); `PRICE` invokes `priceEngine` (Spring bean lookup); `TAX` invokes `taxEngine`.
3. **A fallback credit placeholder is RESOLVED EAGERLY** but only USED if the calling flow zero-ed the primary path's source amount (e.g. for write-off → suspense routing).
4. **Wrong placeholder binding here = wrong GL hit everywhere** that catalogue runs. Always trace via [`08-gl-posting-engine.md §9`](../../08-gl-posting-engine.md).
5. **Hot path during `postTransaction`** — the list is loaded once per call. Cached via accounting Redis (DB 5).
