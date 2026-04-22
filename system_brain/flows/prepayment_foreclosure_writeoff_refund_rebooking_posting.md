# Prepayment / Foreclosure / Write-off / Refund / Rebooking Posting (accounting-v2; non-batch)

## Foreclosure / Prepayment entrypoint: `loanPrepayment`
- Orchestration request: `loanPrepayment` (`loans_orc.xml`)
- Includes **2** nested `postTransaction` calls:
1. `postTransaction` (TRIAL foreclosure)
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="${transaction_sub_type}"`
     - `client_reference_number="${stan}"`
     - `amount="${total_foreclosure_amount}"`
2. `postTransaction` (REAL foreclosure posting)
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="${transaction_sub_type}"`
     - `client_reference_number="${receipt_number}"`
     - `value_date="${foreclosure_date}"`
     - `amount="${total_foreclosure_amount}"`

## Write-off entrypoint: `loanWriteoff`
- Orchestration request: `loanWriteoff` (`loans_orc.xml`)
- Contains **postTransaction** with IParams:
  - `transaction_type="LOAN_WRITE_OFF"`
  - `transaction_sub_type="FINAL_WRITE_OFF"`
  - `client_reference_number="${stan}"`
  - `amount="${principal_amount}"`

## Disbursement cancellation entrypoint: `loanDisbursementCancellation`
- Orchestration request: `loanDisbursementCancellation` (`loans_orc.xml`)
- Contains **2** nested `postTransaction` calls:
1. postTransaction (REAL; non-insurance path)
   - `transaction_type="${transaction_type}"`
   - `transaction_sub_type="${transaction_sub_type}"`
   - `client_reference_number="${receipt_number}"`
   - `value_date="${cancellation_date}"`
   - `amount="${total_cancellation_amount}"`
2. postTransaction (TRIAL)
   - `transaction_type="${transaction_type}"`
   - `transaction_sub_type="${transaction_sub_type}"`
   - `client_reference_number="${stan}"`
   - `value_date="${cancellation_date}"`
   - `amount="${total_cancellation_amount}"`

## Excess/refund entrypoint: `loanAccountExcessAmountRefund`
- Orchestration request: `loanAccountExcessAmountRefund` (`loans_orc.xml`)
- Contains `postTransaction` with:
  - `transaction_type="EXCESS_AMT_REFUND"`
  - `transaction_sub_type="${txn_sub_type}"`
  - `amount="${total_refund_amount}"`

### txn_sub_type selection (code-verified from ORC XML)
- refund_mode != `TRANSFER_TO_INCOME_GL` → dummy sets `txn_sub_type="LOAN_ACCOUNT"`
- refund_mode == `TRANSFER_TO_INCOME_GL` → dummy sets `txn_sub_type="INCOME_GL"`

## Rebooking entrypoint: `loanAccountRebooking`
- Orchestration request: `loanAccountRebooking` (`loans_orc.xml`)
- Contains `postTransaction` with:
  - `transaction_type="LOAN_REBOOKING"`
  - `transaction_sub_type="INTEREST_ADJUSTMENT"`
  - `amount="${txn_amount}"`

## Confidence / gaps
- High: presence of `postTransaction` calls + parameter shapes from orchestration XML traces.
- Medium/UNVERIFIED: exact processor list used to populate `account_details`, `additional_amount_details`, and how each GL/placeholder code maps to these transaction types/subtypes.

