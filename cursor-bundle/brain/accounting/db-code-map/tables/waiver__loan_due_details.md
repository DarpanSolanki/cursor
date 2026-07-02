# `mfi_accounting.waiver__loan_due_details`

> Per-due waiver breakdown. 5 cols. Linkage table — one waiver can clear N due rows.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `loan_due_details_id` | FK → `loan_due_details.id` (the row being waived) |
| `identifier_type`, `identifier_value` | Source event (e.g. `WAIVER_DETAILS` + `waiver_details.id`) |
| `waived_amount` | Money waived from THIS due row |

## Writers

- `updateWaiverLoanDueDetailsProcessor` — INSERT during waiver checker step

## Readers

- 360 view, audit reports

## Related flows

- [Waiver](../../../flows/loan-servicing/waiver.md)

## Gotchas

1. **Generic linkage shape** — `(identifier_type, identifier_value)` lets the same table track waivers from different source events.
2. **Sums up to `waiver_details.waiver_amount`** for that waiver event.
