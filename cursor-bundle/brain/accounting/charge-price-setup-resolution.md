# Reference — Charge / price-setup resolution chain (how every charge code is resolved)

> The master-data chain that turns a charge TYPE into a concrete `charge_code` on a loan, and the
> single gotcha (`is_deleted`) behind the whole "charge shows 0 / not displaying" class.
> Runbook: [`../runbooks/charge-amount-shows-zero.md`](../runbooks/charge-amount-shows-zero.md).
> KG: `kg why <charge>` · `kg table product_scheme__transaction_catalogue__price_setup`.

## The chain

```
loan_account.la_product_scheme_id ──┐
                                     ▼
product_scheme__transaction_catalogue__price_setup   (the per-scheme charge wiring)
   ├─ product_scheme_id      = the loan's scheme
   ├─ transaction_catalogue_id ─► transaction_catalogue (type, sub_type)   ← what KIND of charge
   ├─ price_setup_code         ─► price_setup (code, charge_type, computation_type, tax_group_id, inclusive_of_tax)
   └─ is_deleted              = false  ◄── THE GATE: only an ACTIVE row resolves
```

Resolver (Java): `ProductSchemeDAOService.findPriceSetupCodeByProductSchemeIdAndCatalogueTypeAndSubType(schemeId, type, subType)`
→ native query in `ProductSchemeTransactionCataloguePriceSetupRepository` (`WHERE product_scheme_id=?1 AND tc.is_deleted=false AND ps_tc_ps.is_deleted=false AND tc.type=?2 AND tc.sub_type=?3`). Returns a **single** `price_setup_code` or **null**.

**A charge only appears if `loan_due_details.charge_code == the resolved price_setup_code`.** The due rows are written earlier (billing / SI / penal / batch); the quote just resolves the code and sums the outstanding due rows.

## Charge TYPEs (transaction_catalogue.type) used on the foreclosure / prepayment quote

| Quote line | catalogue `type` | sub_type | Resolver call site (accounting) |
|---|---|---|---|
| **CBC Fee** (cheque/SI bounce) | `CBC` | `DEFAULT` | `FetchLoanForeclosureSimulationDetailsProcessor:221` → `fetchCBCDetails` (also `ValidateLoanPrepaymentDataProcessor:179`) |
| **Foreclosure Fee** | `foreclosure` / `FORCLSR_CHRG` | DEFAULT | `FetchLoanForeclosureSimulationDetailsProcessor:204` (`fetchTransactionalCharges`) |
| **Penal / LPP** | `PENAL` | `DEFAULT` | penal accrual + quote (`PenalInterestAccrualCalculationService`) |
| (others: processing fee, etc.) | per product | DEFAULT | resolved through the same table |

> Tenant note (QA3): the **CBC** code is `SI_Fee` (`price_setup` id 32, name "CBC Charges", `tax_group_id` NULL ⇒ no GST added). Codes are tenant/config data — **always resolve live**, never hardcode.

## The failure mode (why "shows 0")

`findPriceSetupCode...` returns **null** when the scheme has **no ACTIVE mapping** for that type:
- all mapping rows `is_deleted = true` (the QA3 CBC case — 26 deleted, 0 active), or
- the catalogue isn't mapped to that `product_scheme_id`, or
- wrong `type`/`sub_type`.

Downstream the charge is then silently computed as **0.00** (e.g. `cbc_amount = "0.00"` in `fetchCBCDetails` else-branch). No exception. Working schemes have **exactly one** active mapping per charge type.

## Not a source for these charges

`presentation_bounce_charge_details` is the **SI/eNACH bounce ledger** — read only by the SI / recurring-payment / derived-fields **batches** (which create the `loan_due_details` FEE row carrying the CBC `charge_code`). It is **not** read by any foreclosure/prepayment quote. Seeding it does nothing for the quote.

## Live checks

- `db-query.sh mfi_qa3 --canned price-setup-resolution -p scheme=<id> -p type=CBC` (active vs deleted mappings).
- Cross-check a working scheme: it has exactly 1 active row for the same type.
