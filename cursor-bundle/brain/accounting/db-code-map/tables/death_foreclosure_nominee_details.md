# `mfi_accounting.death_foreclosure_nominee_details`

> Confirmed nominee at claim time. 19 cols. Distinct from `loan_account_nominee_details` (which is the *original* nominee bound at disbursement).

## Schema (live, 19 cols)

Mirrors appointee table plus:

| Column | Meaning |
|---|---|
| `is_nominee_changed` | Boolean — true if differs from original |
| `nominee_changed_reason` | Why (e.g. original nominee deceased, dispute) |

(Other 17 cols: `id`, `death_foreclosure_details_id` FK, name/dob/gender/relationship, contact, address, geography, `is_address_same_as_borrower`.)

## Writers

- STAGE_1 of [death-foreclosure](../../../flows/loan-servicing/death-foreclosure.md)

## Readers

- Insurer outbound file builder, 360 view
