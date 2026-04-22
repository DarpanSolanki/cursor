# Edge Case Risk: Interest accrual posting race due to parallel processing + non-deterministic dedupe key

## What’s code-verified (building blocks)
- `interestAccrualPosting` performs per-account posting work in a batch job.
- `InterestAccrualBookingBatchService` generates a **time-based** `client_reference_number` (see:
  - `interest_accrual_posting_client_ref_not_deterministic.md`).

## Risk mechanism (UNVERIFIED dependency)
- If two job executions (or two overlapping partitions/chunks) for the same account/endDate occur concurrently, both attempts may:
  - observe “not fully posted yet”
  - generate different time-based `client_reference_number`
  - call `postTransaction` twice because strict dedupe sees different reference numbers.

## What to verify next
- Confirm how Spring Batch partitions/chunk parallelism is configured for `interestAccrualPosting`.
- Confirm whether job-level concurrency is prevented by scheduler.
- Confirm whether `InterestAccrualBookingItemReader`/writer selection fully prevents overlapping “endDate not posted” records across concurrent runs.

## Confidence
- Medium: requires verifying concurrency/overlap behavior in the job execution configuration.

