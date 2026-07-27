# `mfi_accounting.loan_product_asset_criteria`

> The product ↔ asset-criteria binding **plus** the appropriation precedence + liquidation order. Read by `RepaymentApproppriationProcessor` on every repayment.

## Purpose

For each (loan_product, asset_criteria_slab), defines:
- 4 component slots: which order the engine appropriates incoming repayment across PRIN/INT/PINT/FEE
- Liquidation order: `LIQ_INSTL` (by date), `LIQ_COMP` (by component), or `LIQ_INSTL_CHRG_COMP` (hybrid)

This is the master data behind the entire repayment math.

## Schema (key columns)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `product_id` | FK → `loan_product.id` |
| `asset_criteria_slabs_id` | FK → `asset_criteria_slabs.id` |
| `comp1`, `comp2`, `comp3`, `comp4` | Each one of `APP_LOGIC_PRIN`, `APP_LOGIC_INT`, `APP_LOGIC_PNLT`, `APP_LOGIC_FEES` (constants in `AccountingConstants.java:37-40`) |
| `liquidation_order` | `LIQ_INSTL` / `LIQ_COMP` / `LIQ_INSTL_CHRG_COMP` |
| audit cols | |

## JPA entity

[`product/loanproductassetcriteria/`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/product/loanproductassetcriteria/)

## DAO

[`product/loanproductassetcriteria/repository/LoanProductAssetCriteriaDAOService.java`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/product/loanproductassetcriteria/repository/LoanProductAssetCriteriaDAOService.java)

## Writers

- `createOrUpdateLoanProduct` flow (sub-CRUD inside)
- Direct seed via initial-setup Flyway

## Readers

THE big one:
- [`RepaymentApproppriationProcessor`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java#L71-L79) — `loanProductAssetCriteriaDAOService.getAssetCriteriaSlabDetailsByProductAndAssetCriteriaSlabId(productId, slabId)` returns `(comp1, comp2, comp3, comp4, liquidationOrder)` — the entire appropriation algorithm starts here

Other readers: `PrepaymentApproppriationProcessor` (foreclosure/prepayment).

## Related Requests

- `loanRepayment`, `childLoanRepayment` — primary readers
- `loanForeclosure`, `loanPrepayment`, `individualChildLoanForeclosure` — readers for prepayment appropriation

## Related flows

- [Repayment end-to-end](../../../flows/repayment-end-to-end.md)
- [Posting engine §7](../../08-gl-posting-engine.md#7-the-repayment-appropriation-step-preceeds-posting)
- [Repayment-mismatch runbook](../../../runbooks/repayment-mismatch.md)

## Common queries

```sql
-- Appropriation rule for a (product, slab)
SELECT comp1, comp2, comp3, comp4, liquidation_order
  FROM mfi_accounting.loan_product_asset_criteria
 WHERE product_id = ? AND asset_criteria_slabs_id = ?;
```

## Gotchas

1. **The 4 `comp*` columns are POSITIONAL** — comp1 is settled first, comp2 next, etc. Wrong order = wrong split.
2. **Each `comp*` value is a CODE** (`APP_LOGIC_PRIN` etc.), not a column name. Maps to PRIN/INT/PINT/FEE via `AssetsConstants.APPROPPRIATION_COMPONENT_TYPE_MAP`.
3. **`liquidation_order`** controls within-due ordering:
   - `LIQ_INSTL` — installments first by date, then by comp_precedence
   - `LIQ_COMP` — components first (across installments), then by date
   - `LIQ_INSTL_CHRG_COMP` — split into installment-due (PRIN/INT) by date + charge-due (PINT/FEE) by component
4. **Per-product, per-NPA-slab** — different criteria slabs for the same product can have different appropriation rules (e.g. PINT-first when NPA).
