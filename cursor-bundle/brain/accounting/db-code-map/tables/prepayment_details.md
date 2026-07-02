# `mfi_accounting.prepayment_details`

> One row per prepayment event (foreclosure or full prepayment). 56 cols. Heavy table — captures the full money breakdown including waivers, BPI handling, payment instrument, maker-checker.

## Schema (live, 56 cols — grouped)

### Identity + amounts (gross)
| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `prepayment_amount`, `excess_amount` | Money |
| `round_off_amount` | Final adjustment |
| `foreclosure_date` | Effective date |
| `prepayment_status` | PENDING / APPROVED / REJECTED |
| `is_child_loan_prepayment` | Boolean — SHG/JLG child marker |

### Per-component handling (×4 components, each with these 6 cols)

For each of `pending_installment_*`, `balance_principal_*`, `bpi_*`, `billed_principal_*`:

- `*_amount` — base amount due
- `*_waived_amount` — money waived
- `*_is_waived` — boolean
- `*_is_fully_waived` — boolean
- `*_waiver_percentage` — pct waived
- `*_amount_to_be_paid` — what's actually being paid

### Payment instrument
| Column | Meaning |
|---|---|
| `paid_by`, `depositor_name` | Who paid |
| `payment_mode`, `casa_account_number`, `cheque_number` | Payment channel |
| `merchant_id`, `challan_number`, `challan_number_expiry_date`, `receipt_number`, `ext_ref_number` | External refs |
| `cds_document_id`, `sim_document_id` | Document refs |

### Status / workflow / audit
| Column | Meaning |
|---|---|
| `closure_reason` | masterdata |
| `reject_reason`, `reject_notes` | If rejected |
| `task_id`, `task_status` | Maker-checker |
| `notes`, `request_data` (TEXT) | Free-form / JSON snapshot |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `createPrepaymentDetailsProcessor` — INSERT (PENDING) on maker
- `getPrepaymentDetailsProcessor` — read
- Foreclosure / prepayment checker chain — UPDATE → APPROVED with txn ref

## Readers

- `getLoanForeclosureDetails`, `cancelLoanForeclosure`, `fetchLoanForeclosureSimulationDetails` Requests
- 360 view

## Related Requests

- `loanForeclosure`, `loanPrepayment`, `individualChildLoanForeclosure`, `childLoanForeclosure` — writers
- `getLoanForeclosureDetails`, `getDeathForeclosureDetails` — readers

## Related flows

- [Foreclosure & closure](../../../flows/foreclosure-and-closure.md) — primary writer
- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md) — for death-driven full prepayment

## Sister table

- [`prepayment_charge_details`](prepayment_charge_details.md) — per-charge breakdown linked to a prepayment row

## Gotchas

1. **The 4 component sets** (`pending_installment_*`, `balance_principal_*`, `bpi_*`, `billed_principal_*`) all follow the same 6-column shape. Reading the table requires understanding which set applies to your scenario.
2. **`request_data`** is a JSON snapshot of the original request payload — useful for debugging "what did the maker actually submit?".
3. **Each waiver-related column applies per-component** — partial waivers possible.
