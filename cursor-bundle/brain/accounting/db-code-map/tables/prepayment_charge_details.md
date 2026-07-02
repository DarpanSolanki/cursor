# `mfi_accounting.prepayment_charge_details`

> Per-charge breakdown for a prepayment event. 18 cols. One row per charge applied (foreclosure charge, NOC charge, etc.) linked to a `prepayment_details` row.

## Schema (live, 18 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `prepayment_details_id` | FK → `prepayment_details.id` |
| `charge_code`, `charge_name` | masterdata |
| `charge_rate`, `charge_fixed_amount`, `base_amount` | Calc inputs |
| `charge_amount` | Computed amount |
| `is_waived`, `is_fully_waived`, `waived_amount`, `waived_percentage` | Waiver fields |
| `amount_to_be_paid` | Net charge after waiver |
| `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `createPrepaymentChargeDetailsProcessor` — INSERT during foreclosure / prepayment maker step

## Readers

- Foreclosure / prepayment checker — reads to compute totals + post GL legs
- `populateAdditionalTaxAmountAndAccountDetailsFromChargeDetails` — joins with tax details

## Related flows

- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md)

## Gotchas

1. **One charge can be partially waived** — `waived_amount < charge_amount`, `is_fully_waived=false`.
2. **Linked to prepayment_details, not loan_account directly** — to find charges for a loan, JOIN through `prepayment_details`.
