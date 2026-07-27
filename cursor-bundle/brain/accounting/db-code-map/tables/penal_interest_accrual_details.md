# `mfi_accounting.penal_interest_accrual_details`

> Sibling of `interest_accrual_details` for **penal** (overdue) interest.

## Purpose

Same shape as `interest_accrual_details`, but for penal interest accrual driven by DPD × penal slabs (per `loan_product_asset_criteria` + asset criteria slab settings).

## Schema

Mirrors `interest_accrual_details` (account_id, base_amount, start/end_date, interest_rate, total_*_amount, last_accrual_posted_date). Verify columns with `tools/inspect-table.sh penal_interest_accrual_details`.

## Writers

- [`PenalInterestAccrualCalculationItemWriter`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/penal/) — INSERT
- [`PenalInterestAccrualBookingItemWriter`](../../../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/penal/penalaccrualbooking/PenalInterestAccrualBookingItemWriter.java) — UPDATE + posts to GL via `postTransaction` and INSERTs PINT rows in `loan_due_details`

## Readers

- `PenalInterestAccrualBookingItemReader` — pulls unposted rows for posting

## Related Requests

- `penalInterestAccrualCalculation`, `penalInterestAccrualBooking` — fired by `runEODJobs`

## Related flows

- [EOD/BOD cycle](../../../flows/eod-bod-cycle.md)
- [NPA & provisioning](../../../flows/npa-and-provisioning.md)

## Gotchas

1. **Booking creates new `loan_due_details` rows** with `component_type='PINT'` — that's how penal becomes payable.
2. **Penal slab rate** comes from `asset_criteria_slabs.penal_interest_rate` (or similar) — varies by NPA bucket.
3. **Same idempotency story** as regular accrual: keyed on (account_id, period); UPSERT.
