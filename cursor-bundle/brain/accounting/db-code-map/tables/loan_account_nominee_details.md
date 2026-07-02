# `mfi_accounting.loan_account_nominee_details`

> Per-loan nominee. 8 cols. Used during death-foreclosure to identify the rightful claimant. Linked to `loan_account_insurance_details` via `insurance_id`.

## Schema (live, 8 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `nominee_name`, `date_of_birth`, `gender` | Nominee identity |
| `nominee_rel_to_insured` | Relationship masterdata code |
| `insurance_id` | FK → `loan_account_insurance_details.id` |
| `is_deleted` | Soft-delete |

## Writers

- `disburseLoan` chain (if nominee provided)
- `createOrUpdateLoanAccountProcessor` extensions

## Readers

- Death-foreclosure flow (`syncDetailsForDeathForeclosureProcessor` reads to populate the death-fc record)
- 360 view

## Related flows

- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md) — heaviest reader
- [Disbursement](../../../flows/disbursement-end-to-end.md) — usual writer

> **Note:** distinct from `death_foreclosure_nominee_details` — that one captures the nominee details *as confirmed* during the death-claim flow (which may differ from the original).
