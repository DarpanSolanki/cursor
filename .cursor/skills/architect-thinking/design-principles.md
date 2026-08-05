<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.md only routes here. -->

# Architect-level thinking

## Design before code

- Before implementing, think: What are the failure modes? What happens on retry? What if the downstream service is down? What if this runs concurrently?
- For any new feature: draw the data flow mentally (or explain it). Which services are involved? What are the transaction boundaries? Where can partial failure happen?
- Ask: "If this runs in production with 10K concurrent users and one service is slow, what happens?"

## Distributed systems awareness

- **Partial failure**: When MS A calls MS B then MS C, if C fails, B's changes are already committed. Design compensating actions or make C idempotent.
- **Eventual consistency**: Kafka-based flows are eventually consistent. The consumer may process hours later. Design for the gap.
- **Idempotency**: Every write endpoint and consumer must be safe to replay. Use status checks, upserts, or idempotency keys.
- **Ordering**: Kafka partitions guarantee order within a partition. Use meaningful partition keys (e.g. `external_ref_number` for loan-level ordering).
- **Timeouts and retries**: Bank API calls can timeout. The transaction may have succeeded on the bank side. Always implement inquiry/callback before assuming failure.

## Performance thinking

- **Think in batch sizes**: If processing 1000 loans, don't make 1000 DB calls. Batch with `IN (...)` or `UNNEST`. Stream results if they don't fit in memory.
- **Index awareness**: Before writing a WHERE clause, ask: is there an index on this column? If not, should there be?
- **Connection pool**: Each DB call uses a connection. N+1 queries exhaust pools under load. One query with JOIN is one connection use.
- **Async where possible**: Bank callbacks, notifications, and non-critical updates can be Kafka-async. Don't block the user's API call.

## Error classification

- **Validation error** (user's fault): Fail-fast, clear message, no retry. `NovopayFatalException`.
- **Business rule violation** (system state): Fail with clear error code. No retry.
- **Transient failure** (network, lock, timeout): Retry with backoff. `NovopayNonFatalException` or `@Retryable`.
- **Infrastructure failure** (DB down, Kafka down): Circuit-break or degrade gracefully. Alert.
- **Data inconsistency** (shouldn't happen): Log with full context, alert, and fail rather than silently proceeding with wrong data.

## When reviewing or changing code, think like an architect

1. **Blast radius**: How many flows/modules does this change affect?
2. **Rollback plan**: If this goes wrong in production, can we revert cleanly?
3. **Monitoring**: How will we know if this change causes problems? (logs, metrics, alerts)
4. **Data migration**: If schema changes, what about existing data?
5. **Feature flag**: Should this be behind a flag for gradual rollout?


## Growth mindset

- When you encounter a pattern you don't fully understand, name it and note it for study.
- When you see a better way to do something, propose it (but don't force it into the current change).
- Learn the "why" behind every framework choice — why native queries? why orchestration XML? why not @Transactional?
- Study production incidents — they teach more than textbooks.
- Read the infra-lib source code when behavior is unclear. The source is in `trustt-platform-lib/`.

---

