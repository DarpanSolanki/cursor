# `mfi_accounting.loan_account_part_prepayment_details`

> One row per part-prepayment event (PENDING → APPROVED). 31 cols. Captures the proposed schedule diff + payment instrument + maker-checker audit.

## Schema (live, 31 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `loan_account_id` | FK |
| `rescheduling_effective_date` | When the new schedule takes effect |
| `part_prepayment_impact` | `REDUCE_TENOR` / `REDUCE_EMI` |
| `broken_period_interest_handling` | `UPFRONT` / `NO` |
| `bpi_amount` | Broken-period interest |
| `due_amount`, `overdue_amount`, `overdue_fee_charges` | Pending amounts at request time |
| `charges`, `net_amount`, `gross_amount` | Money breakdown (gross = net + charges) |
| `status` | PENDING / APPROVED / REJECTED |
| `instrument_type`, `receipt_number`, `cds_document_id` | Payment instrument + receipt audit |
| `paid_by`, `depositor_name` | Who paid (PAID_BY masterdata) |
| `task_id`, `task_status` | Maker-checker task linkage |
| `approved_on`, `approved_by`, `created_*`, `updated_*` | Audit |
| `external_ref_no_1`, `external_ref_no_2` | External integrations |
| `expiry_date` | Quote expiry |
| `notes`, `comments` | Free-form |

## Writers

- `createOrUpdateLoanAccountPartPrepaymentProcessor` — INSERT (PENDING) on maker, UPDATE (APPROVED) on checker
- `populateLoanAccountPartPrepaymentDetailsProcessor` — read; updates EC

## Readers

- `getLoanAccountPartPrepaymentDetails` Request
- `validatePendingLoanAccountPartPrepaymentProcessor` (refuses concurrent prepayments per loan)

## Related flows

- [Part-prepayment flow](../../../flows/loan-servicing/part-prepayment.md)

## Common queries

```sql
-- Active part-prepayments
SELECT a.account_number, lpd.status, lpd.gross_amount, lpd.part_prepayment_impact, lpd.created_on
  FROM mfi_accounting.loan_account_part_prepayment_details lpd
  JOIN mfi_accounting.loan_account la ON la.account_id = lpd.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE lpd.status = 'PENDING' ORDER BY lpd.created_on;
```
