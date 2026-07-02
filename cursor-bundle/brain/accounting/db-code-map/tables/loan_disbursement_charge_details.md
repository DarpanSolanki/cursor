# `mfi_accounting.loan_disbursement_charge_details`

> Per-charge breakdown bound at disbursement (e.g. processing fee, documentation charge, insurance premium). 20 cols.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `charge_code`, `charge_name`, `charge_identifier` | masterdata + per-charge identifier |
| `charge_rate`, `charge_fixed_amount`, `base_amount`, `charge_amount` | Calc + result |
| `is_waived`, `is_fully_waived`, `waived_amount`, `waived_percentage`, `amount_to_be_paid` | Waiver fields |
| `is_inclusive_of_loan_amount` | Boolean — was charge added to loan_amount or deducted from disbursement? |
| `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- Disbursement chain (`disburseLoan` DEFAULT/LAN_CREATED stages) — INSERT one row per applicable charge

## Readers

- `disburseLoan` charge computation
- 360 view, `getLoanAccountAppliedCharges`

## Related flows

- [Disbursement end-to-end](../../../flows/disbursement-end-to-end.md)

## Gotchas

1. **`is_inclusive_of_loan_amount=true`** — charge added to loan principal (customer pays interest on it). False = deducted at disbursement (customer receives less).
2. **`charge_identifier`** distinguishes multiple instances of the same charge_code on one loan.
