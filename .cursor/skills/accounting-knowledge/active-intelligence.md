<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

# Accounting Module — Active Intelligence

## Before editing any file in this module, you already know

- Full flow map: `.cursor/accounting-flows.md`
- All active gaps in this module: check `gaps-and-risks-digest.md` (High verbatim; escalate to full `gaps-and-risks.md` when GAP-id/area flagged)
- Events this module produces/consumes: `.cursor/event-registry.md`
- Redis keys used here: disburse consumer `dl{originalKey}` / in-flight pattern — atomic owner-token acquire, configurable TTL (`mfi.disburse.loan.consumer.lock.ttl.ms`, default 600000 ms), and compare-and-delete release
- Entry points: `ServiceGatewayController` (HTTP) + `LmsMessageBrokerConsumer` (Kafka) + `BulkCollectionFailedRecordConsumer`
- Entity/orchestration depth: see `accounting-flows.md` and `architecture.md` §3 (do not assume a single entity count without checking the doc)

## Auto-checks before any edit

1. Does this file touch a money path? → check `accounting-flows.md` for this flow
2. Does this file touch a Kafka consumer? → check for swallow pattern (exception handling / offset commit)
3. Does this file touch Redis? → verify TTL / cleanup / replay safety
4. Does this file touch a batch writer? → check idempotency (`client_reference_number`, staging flags)
5. Is there an existing gap for this area? → check `gaps-and-risks-digest.md` (escalate to full `gaps-and-risks.md` when GAP-id/area flagged)

## After any edit to this module

- Update `.cursor/accounting-flows.md` if flow changed
- Update `.cursor/event-registry.md` if event changed
- Update `.cursor/gaps-and-risks.md` if gap resolved or introduced
- Update the matching topic file under `.cursor/skills/accounting-knowledge/` per **Accounting knowledge sync**
- Append `.cursor/changelog.md` — **mandatory**

## Active High-risk themes in this module (never ignore — verify in `gaps-and-risks-digest.md`; escalate to full SoT when flagged)

- `entity_type` missing from disbursement sync payload vs LOS consumer
- Redis consumer / LOS-related dedupe locks use TTL + owner-safe release on the TDPQA-54 working tree; preserve atomic acquire and fail-closed replay decisions
- Async disburse / Kafka result path error handling and tests
- Batch posting **time-based** `client_reference_number` / replay
- GL zeroisation, reversal, manual JE — test and contract safety


---

