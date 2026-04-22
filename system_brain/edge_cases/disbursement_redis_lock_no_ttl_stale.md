# Edge Case Risk: Disbursement Redis in-flight marker has no TTL (stale lock → stuck replay)

## What’s code-verified
- LOS producer (`DisburseLoanAPIUtil#callDisburseLoanAPI`) sets a Redis marker:
  - `novopayCacheClient.set(tenant, cacheKey, "in_progress", RedisDBConfig.ACCOUNTING)`
  - with **no TTL** (no expiry set).
- Accounting consumer (`LmsMessageBrokerConsumer`) uses a separate lock key:
  - `dl + originalCacheKey`
  - also set **without TTL**.
- Cleanup happens in consumer `finally`, but only if the JVM/thread reaches cleanup.

## Risk mechanism
- If the consumer crashes/hangs after setting the in-flight key but before `finally` cleanup runs, the “in progress/lock” key may remain indefinitely.
- Subsequent replays may be skipped due to the Redis lock presence (`LOCK_CACHE_IN_PROGRESS`).

## What to verify (UNVERIFIED operational assumption)
- How consumer crashes/timeouts are handled in production (container restart behavior, max poll time, rebalancing).

## Confidence
- High for “no TTL + skip on lock key” mechanics.
- Medium for the operational “stale lock leads to stuck” likelihood (depends on runtime recovery).

