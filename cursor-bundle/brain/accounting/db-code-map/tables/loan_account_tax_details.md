# `mfi_accounting.loan_account_tax_details`

> Per-event tax record (e.g. GST on a foreclosure charge). 12 cols. Linked to a source event via `event` + `identifier_id`.

## Schema (live, 12 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `event` | Source event type (e.g. `FORECLOSURE`, `PART_PREPAYMENT`) |
| `identifier_id` | FK into the event-specific table (e.g. `prepayment_details.id`) |
| `code`, `name` | Tax component info (`tax_component.code`) |
| `rate`, `amount` | Tax rate + computed amount |
| `inclusive_of_tax` | Boolean — whether base was inclusive |
| `external_reference_id` | Tax-authority reference |
| `tax_calculator_adaptor` | Strategy class used (Internal/External/Inclusive/Exclusive) |
| `is_reversed` | Boolean |
| `gst_invoice_number` | If GST invoice generated |

## Writers

- `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails` — populates EC + writes
- `createPartPrepaymentTaxDetailsProcessor`
- Tax engine (`TaxEngine`) — invoked during `postTransaction` rule execution
- `updateLoanAccountTaxDetailsExternalReferenceIdProcessor` — adds GST invoice ref after generation

## Readers

- `getLoanAccountAppliedCharges`, `getForeclosureChargeDetails` Requests
- Tax reporting (RBI returns)

## Related Requests

- `loanForeclosure`, `loanAccountPartPrepayment`, `loanDisbursementCancellation`, `disburseLoan` — all create rows
- `getLoanAccountApplicableCharges`, `getLoanAccountAppliedCharges` — readers

## Related flows

- All money-movement flows in [`../../../flows/loan-servicing/`](../../../flows/loan-servicing/)
- [Posting engine §3 phase 1](../../08-gl-posting-engine.md#3-executetransactionrulesprocessor--the-engine-itself) — TaxEngine invocation

## Gotchas

1. **Linked via `(event, identifier_id)` pair**, not a hard FK — generic shape works across foreclosure/prepayment/cancellation events.
2. **`is_reversed=true`** when the parent transaction is reversed — keeps the row but marks it inactive.
