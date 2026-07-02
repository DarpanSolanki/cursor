# `mfi_accounting.loan_disbursement_cancellation_details`

> One row per disbursement-cancellation event. 42 cols. Heaviest cancellation table — captures money breakdown, BPI handling, payment mode, insurance cancellation status.

## Schema (live, 42 cols — selected)

### Money
| Column | Meaning |
|---|---|
| `total_cancellation_amount`, `round_off_amount`, `principal_outstanding_amount`, `excess_amount`, `cross_sell_amount` | Money breakdown |
| `bpi_amount`, `bpi_waived_amount`, `bpi_is_waived`, `bpi_is_fully_waived`, `bpi_waiver_percentage`, `bpi_amount_to_be_paid` | BPI handling |

### Workflow / payment
| Column | Meaning |
|---|---|
| `cancellation_date` | Effective date |
| `cancellation_reason` | masterdata |
| `cancellation_status` | PENDING / APPROVED / REJECTED / PROCESSED |
| `paid_by`, `depositor_name`, `payment_mode`, `casa_account_number`, `cheque_number` | Payment instrument |
| `merchant_id`, `challan_number`, `challan_number_expiry_date`, `receipt_number`, `ext_ref_number` | External refs |
| `cds_document_id`, `sim_document_id`, `cancellation_letter_document_id` | Document refs |

### Insurance + workflow + audit
| Column | Meaning |
|---|---|
| `insurance_cancellation_status` | NOT_REQUIRED / PENDING / SENT / CONFIRMED / FAILED |
| `task_id`, `task_status`, `reject_reason`, `reject_notes`, `notes` | Workflow |
| `approved_*`, `created_*`, `updated_*`, `is_deleted` | Audit |

## Sister tables

- [`loan_disbursement_cancellation_charge_details`](loan_disbursement_cancellation_charge_details.md) — per-charge waivers
- `loan_disbursement_cancellation_details__document` — supporting docs
- `disbursement_cancellation_insurance_staging_details` (39 cols) — outbound/inbound to insurer

## Writers

- `createOrUpdateLoanDisbursementCancellationProcessor` — INSERT (PENDING)
- `updateLoanDisbursementCancellationProcessor` — UPDATE (APPROVED) on checker
- Insurance flows — UPDATE `insurance_cancellation_status`

## Readers

- `getDisbursementCancellationDetails`, `fetchDisbursementCancellationSimulationDetails` Requests
- `populateDisbursementCancellationParentAccountDetailsProcessor` (SHG/JLG parent reschedule reads to know what was cancelled)

## Related flows

- [Disbursement cancellation](../../../flows/loan-servicing/disbursement-cancellation.md)
