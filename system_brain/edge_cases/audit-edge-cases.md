# novopay-platform-audit — Edge cases (Wave 4)

**Date:** 2026-04-10

- **GAP-057** — `AuditMessageBrokerConsumer#parseData`: parse failure returns **empty** JSON → **silent skip** of ES indexing.
- **No Redis** — audit service does not use infra-cache (per service CLAUDE).
- **STAN replay** — `getApiResponseByStan` depends on `response_log` ingestion; if gateway response Kafka lags, idempotent retry may not find stored body.
