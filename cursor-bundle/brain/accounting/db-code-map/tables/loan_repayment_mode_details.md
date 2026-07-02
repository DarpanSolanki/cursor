# `mfi_accounting.loan_repayment_mode_details`

> Per-loan, the mandate target — where repayment is auto-debited from. 15 cols. Mirrors `loan_disbursement_mode_details` but for repayment direction.

## Schema

`id`, `loan_account_id`, `mode` (NACH/eNACH/STANDING_INSTRUCTION/CASH), `account_type`, `account_number`, `account_holder_name`, `routing_type`, `routing_value`, `bank_name`, audit cols.

## Writers

- `disburseLoan` chain (mandate captured at disbursement)
- `getLoanRepaymentModeDetailsProcessor` — read

## Readers

- `eNACH` flow + `SI` flow — reads to know which account to debit
- 360 view

## Related flows

- [Disbursement](../../../flows/disbursement-end-to-end.md) — set here
- (Mandate flows are tier-3 — covered in [`../00-INDEX.md`](../00-INDEX.md) tier 3 list; use `inspect-table.sh` for `enach_*` and `si_*` schemas)
