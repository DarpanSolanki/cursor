# Edge Case Risk: Proactive excess refund writer swallows exceptions (idempotency undermined)

## What’s code-verified
- Batch: `ProactiveExcessAmountRefundJob` writes proactive refund results and calls internal `postTransaction` for `transaction_type = EXCESS_AMT_REFUND`.
- Exception handling (writer-level):
  - `ProactiveExcessAmountRefundItemWriter` catches `Exception e` and only logs `LOG.debug(...)` without rethrowing and without guaranteeing the staging row is updated to a “failed” state.

## Why this can break replay safety
- The writer’s “stage row state” is what prevents the reader from picking the same staging record again.
- If `postTransaction` partially succeeds and the writer then hits the swallowed exception before it sets `is_deleted=true` / success marker (or `...fail=true`), then:
  - the staging row can be re-picked in a later rerun
  - since `client_reference_number` is time-based in this job, strict `client_reference_number` dedupe may not block re-posting.

## What to verify next (UNVERIFIED operational scenario)
- Whether `postTransaction` can commit ledger rows while the subsequent staging update fails in the same attempt (transaction boundary / exception boundary).
- Whether the batch framework wraps writer calls in a transaction that rolls back both ledger posting and staging row updates together.

## Confidence
- High: exception swallowing behavior is verified in the writer.
- Medium/UNVERIFIED: the partial-commit re-post scenario depends on transaction boundaries.

