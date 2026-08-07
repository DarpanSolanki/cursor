# `novopay-platform-audit` — Centralised request/response logging + functional audit search

> Two storage planes. **DB** (`request_log`, `response_log`) is keyed by STAN (System Trace Audit Number) and used for replay/idempotency. **Elasticsearch** holds the functional audit (the human-meaningful "who did what to which entity, when") and powers the audit-search UI.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.audit` |
| DB schema | `mfi_audit` |
| Elasticsearch index | tenant-scoped via `novopay.platform.es.audit.index.prefix` |
| Repo | [`novopay-platform-audit/`](../../novopay-platform-audit/) |
| Service .cursorrules | [`trustt-platform-audit/.cursorrules`](../../trustt-platform-audit/.cursorrules) |

## API surface

`ServiceOrchestrationXML.xml` (92 lines) — 7 Requests:
- `postAuditData` — write functional audit
- `getAuditEsDataByQuery`, `getAuditEsDataByUserStory` — ES search
- `getAuditDetails`, `getAuditDetailsForUsers`, `getLatestAuditDataForUsers` — DB lookups
- `getApiResponseByStan` — **idempotent retry** (returns the prior response for the same STAN)

## Kafka

**No producer.** Consumer-only — drains audit events from the gateway and other services:

| Consumer | Topic prefix |
|---|---|
| Gateway request log | `api_gateway_request_*` |
| Gateway response log | `api_gateway_response_*` |
| Functional audit | `audit_*` |
| Telemetry | `telemetry_perf_log_*` |
| External-service audit | `external_service_audit_*` |

## Outbound HTTP

- task — `getTimelineAction` to enrich audit data with workflow context. Skipped when `function_code = WITHOUT_TIMELINE`.

## Inbound

Anyone querying audit data (UI dashboards, compliance, analyst tools). Plus `getApiResponseByStan` callers that need idempotent retry guarantees (e.g. gateway dedup, payment callback handlers).

## DB clusters

| Cluster | Tables | Purpose |
|---|---|---|
| Request/response | `request_log`, `response_log` | STAN-keyed; full payload of each gateway call |
| External service | `external_service_details` | 3rd-party API call audits |
| Telemetry | `telemetry_log` | Per-call perf metrics + channel info |

## Concepts owned

- **STAN** — system-wide unique trace number per gateway request. Used for dedup, replay, and cross-service correlation.
- **Functional audit** — entity-level "X changed Y from old → new at T". Stored only in ES (DB log is the *transport*; ES is the *search*).
- **Timeline action** — workflow context tags (e.g. "approval", "reject"). Enriched from task service.

## Known gotchas

1. **Dual storage** — DB for transport (STAN-keyed), ES for search. Always know which one you're querying.
2. **`getApiResponseByStan` reads only `response_log`** — if the gateway-response Kafka topic is lagged, the response row may not yet exist; idempotent retries can return "not found" briefly after a successful call.
3. **ES index is per-tenant** — multi-tenant queries need explicit tenant context.
4. **`function_code = WITHOUT_TIMELINE`** skips the task call — used for high-throughput / non-workflow events.
