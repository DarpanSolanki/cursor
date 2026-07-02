# Runbook — a charge / fee / amount shows ₹0.00 (or blank) on a quote/preview screen

> The **config-resolution** failure class. Symptom: a computed amount (CBC fee, foreclosure fee, penal,
> any charge) renders 0/blank on a foreclosure/prepayment/quote/simulation screen even though the
> transactional rows exist. General method: [`pinpoint-rca-playbook.md`](pinpoint-rca-playbook.md).
> KG: `kg why <request>` and `kg why <charge-keyword>`.

## The mechanism (why it silently becomes 0)

A charge line on a quote is produced by a **resolver** that maps the charge to a **price-setup code** on the loan's product scheme, then reads the matching due rows:

```
findPriceSetupCodeByProductSchemeIdAndCatalogueTypeAndSubType(schemeId, <TYPE>, <SUBTYPE>)
   → product_scheme__transaction_catalogue__price_setup  (is_deleted = false)     ← the gate
       JOIN transaction_catalogue (type=<TYPE>, sub_type=<SUBTYPE>, is_deleted=false)
       → price_setup.code   (the resolved charge_code)
   → loan_due_details WHERE charge_code = <resolved code> AND due_amount > paid+waived
                        AND due_date <= as-of date AND is_deleted=false
```

If the resolver returns **null** (no *active* mapping on that scheme), the charge is silently set to **0.00** — no error. See [`../accounting/charge-price-setup-resolution.md`](../accounting/charge-price-setup-resolution.md) for the full chain + every charge TYPE.

## Diagnose (live, in order)

1. **Resolve which Request serves the screen** and which charge is 0 (`kg why <request>`; e.g. foreclosure quote = `fetchLoanForeclosureSimulationDetails`).
2. **Check the price-setup mapping on the loan's product scheme — INCLUDING `is_deleted`:**
   ```sql
   -- canned: db-query.sh mfi_qa3 --canned price-setup-resolution -p scheme=<id> -p type=CBC
   SELECT ps.id, ps.price_setup_code, tc.type, tc.sub_type, ps.is_deleted
   FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup ps
   JOIN mfi_accounting.transaction_catalogue tc ON tc.id = ps.transaction_catalogue_id
   WHERE ps.product_scheme_id = <SCHEME> AND tc.type = '<TYPE>'      -- CBC | foreclosure | PENAL | ...
   ORDER BY ps.is_deleted;
   ```
   - **0 active rows** (all `is_deleted=true`, or none mapped) → resolver returns null → **this is the cause**. Compare with a scheme that renders the charge (it will have exactly **1 active**).
3. **Confirm the due row exists with the RESOLVED code:**
   ```sql
   SELECT component_type, charge_code, due_amount, paid_amount, waived_amount, due_date
   FROM mfi_accounting.loan_due_details
   WHERE loan_account_id = <id> AND charge_code = '<resolved price_setup_code>';
   ```
   The displayed amount = `Σ(due_amount − paid − waived)` over matching, outstanding, due-on/before-date rows.

## Fix (config, not code)

Give the scheme **exactly one active** mapping for that charge TYPE (mirror a working scheme):
```sql
UPDATE mfi_accounting.product_scheme__transaction_catalogue__price_setup
SET is_deleted = false, updated_by = 'QA_SETUP', updated_on = now()
WHERE id = <one soft-deleted mapping id for this scheme+catalogue>;
-- verify exactly 1 active (resolver returns a single value; >1 active risks NonUniqueResult):
SELECT count(*) FROM mfi_accounting.product_scheme__transaction_catalogue__price_setup
WHERE product_scheme_id=<SCHEME> AND transaction_catalogue_id=<CAT_ID> AND is_deleted=false;
```
Then the existing `loan_due_details` rows surface as the charge. **No code change.**

## Worked example (proven QA3, 2026-06-11)

LAN 6008846130 / scheme 1 — CBC Fee ₹0.00 on the foreclosure screen. CBC code in this tenant = `SI_Fee` (`price_setup` id 32 "CBC Charges"). Scheme 1 had **26** CBC→SI_Fee mappings, **all `is_deleted=true`** → 0 active → resolver null → CBC hard-zeroed in `FetchLoanForeclosureSimulationDetailsProcessor.fetchCBCDetails`. The seeded `loan_due_details` (SI_Fee, due 90000, waived 12) and `presentation_bounce_charge_details` rows were correct; `presentation_bounce_charge_details` is **not** read by the quote (SI bounce ledger, batch-only). Fix: activate one CBC→SI_Fee mapping → CBC Fee = ₹89,988 (90000 − 12 waived).

`kg why cbc` · `kg why fetchLoanForeclosureSimulationDetails` for the catalogued version.
