# `mfi_accounting.loan_account_charge_details`

> Per-loan applied-charges register. 16 cols. One row per charge bound at disbursement / part-prepayment / foreclosure (charges that the customer must pay).

## Schema (live, 16 cols)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `charge_code` | masterdata reference (e.g. `FORECLOSURE_CHARGE`, `BOUNCE_CHARGE`) |
| `charge_type` | FIXED / PERCENT / SLAB |
| `charge_value` | Rate or fixed amount |
| `min_amount`, `max_amount` | Slab caps |
| `from_tenure`, `to_tenure` | Applicable tenure window (months) |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `loan/charges/processor/...` — INSERT during disbursement, foreclosure, prepayment
- Charge-specific processors (e.g. bounce-charge job)

## Readers

- `fetchLoanAccountChargeDetails` Request
- Servicing flows that compute charges (foreclosure, prepayment) read this for applicable rates

## Related Requests

- `disburseLoan` (writer), `loanForeclosure`, `loanAccountPartPrepayment` (readers + writers)
- `fetchLoanAccountChargeDetails`

## Related flows

- [Disbursement](../../../flows/disbursement-end-to-end.md), [Foreclosure](../../../flows/foreclosure-and-closure.md), [Part-prepayment](../../../flows/loan-servicing/part-prepayment.md)
