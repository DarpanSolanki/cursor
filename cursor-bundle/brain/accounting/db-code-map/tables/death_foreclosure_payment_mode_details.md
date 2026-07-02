# `mfi_accounting.death_foreclosure_payment_mode_details`

> How nominee receives any refund (excess + insurance settlement). 8 cols.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `death_foreclosure_details_id` (FK) | |
| `account_type` | SAVINGS / CURRENT |
| `bank_code`, `account_number`, `account_holder_name` | Bank details |
| `routing_type`, `routing_value` | IFSC / etc. |

## Writers

- STAGE_1 (`createOrUpdateDeathForeclosurePaymentModeDetailsProcessor`)

## Readers

- Death-fc final close (STAGE_6) reads to issue refund to nominee
- [Excess amount refund](../../../flows/loan-servicing/excess-amount-refund.md) — uses these details for the auto-refund
