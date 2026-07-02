# `mfi_accounting.loan_disbursement_cancellation_charge_details`

> Per-charge waiver/refund breakdown for a cancellation event. 18 cols. Mirrors `prepayment_charge_details` shape.

## Schema

`id`, `loan_disbursement_cancellation_details_id` (FK), `charge_code`, `charge_name`, `charge_rate`, `charge_fixed_amount`, `base_amount`, `is_waived`, `is_fully_waived`, `charge_amount`, `waived_amount`, `waived_percentage`, `amount_to_be_paid`, `created_*`, `updated_*`, `is_deleted`.

## Writers

- `loan/cancellation/processor/...` during disbursement-cancellation maker step

## Related flows

- [Disbursement cancellation](../../../flows/loan-servicing/disbursement-cancellation.md)
