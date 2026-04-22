# Edge Case Risk: Lock recovery sets `loan_status=LOCK` but does not update `disbursement_status`

## What’s code-verified
- Lock recovery path: `ClientRequestResponseLogDAOService#recover(...)`
  - sets `loan_account.loan_status = LOCK`
  - sets filler fields describing audit/log save failure
- Not found in code:
  - a corresponding update of `loan_account.disbursement_status` in this lock recovery path.

## Risk mechanism (UNVERIFIED dependency)
- If replay/resubmission relies on `loan_account.disbursement_status` to decide the correct stage to resume, then a “LOCK” without stage update could cause:
  - incorrect stage selection
  - repeated retries until an operator reset (or stage re-initiation logic kicks in)

## What to verify next
- In disbursement resumption processors, whether stage routing uses:
  - `loan_status`
  - `disbursement_status`
  - or both (and with what precedence).

## Confidence
- High: lock recovery behavior (no disbursement_status write).
- Medium/UNVERIFIED: the downstream stage-routing consequence.

