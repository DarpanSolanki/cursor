# Edge Case Risk: Interest accrual posting dedupe defeated by time-based `client_reference_number`

## What’s code-verified
- `interestAccrualPosting` calls accounting internal `postTransaction`.
- `InterestAccrualBookingBatchService#doInterestBooking(...)` sets:
  - `exec.putLocal("client_reference_number", accountId + "" + new Date().getTime())`
  - so `client_reference_number` changes on each retry/run.
- `postTransaction` dedupe guard:
  - `ClientReferenceNumberDedupProcessor` searches for existing `TransactionMasterEntity` by `(client_code, client_reference_number)`
  - if found, it throws `NovopayFatalException("134067", "Duplicate client_reference_number")`.

## Why this is a replay risk
- Because the dedupe key is time-based, **retries may generate a new `client_reference_number`**, meaning the strict dedupe processor cannot detect “same accrual period posted already”.

## What to verify (UNVERIFIED dependency)
- Whether batch writer execution boundaries can cause `postTransaction` to commit while later updates (e.g. saving updated `interest_accrual_details` posting totals/dates) fail in the same chunk/job attempt.
- If they can commit partially, then a retry could double-post GL entries.

## Confidence
- High: time-based `client_reference_number` + strict dedupe guard are confirmed in code.
- Medium/UNVERIFIED: the partial-commit scenario requires confirming transactional boundaries for the batch step/writer.

