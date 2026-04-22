# Edge Case Risk: NEFT Stage-2 initiation depends on `disbursement_status` in context

## What’s code-verified
- `CallBankAPIForDisbursementProcessor` has logic to decide whether to skip NEFT stage-2 initiation:
  - it reads `disbursementStatus = executionContext.getValue(DISBURSEMENT_STATUS, String.class)`
  - it only considers stage-2 skip when `disbursementStatus == NEFT_STAGE_2_PENDING`
  - it then checks for the existence of a successful prior `DISBURSEMENT_NEFT_NEI` CRR entry.

## Risk mechanism (UNVERIFIED dependency)
- If replay/resubmission passes a context where `DISBURSEMENT_STATUS` is missing or mismatched to the persisted `loan_account.disbursement_status`,
  - the stage-2 skip condition may not trigger,
  - causing NEI initiation to be retried even when it should be skipped.

## What to verify next
- Confirm whether stage routing uses:
  - persisted `loan_account.disbursement_status` (via DB reads) vs
  - only `executionContext` values at that processor.

## Confidence
- Medium: skip-gate behavior is confirmed; mismatch-caused duplication depends on how context is populated in each replay path.

