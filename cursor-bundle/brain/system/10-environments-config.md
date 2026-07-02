# 10 · Environments, tenants, config

## Tenant model

- Single cluster, multi-schema. Tenant codes seen in code: `mfi` (primary), plus `idfcp`, `product`, `waas`, `bp`, `fk`, `nl` (per actor's tenant-specific orchestration XMLs).
- **Tenant resolution** at gateway (`InitialFilter`) → `ThreadLocalContext.setTenant(PlatformTenant)`. Propagated through every downstream call.
- **Per-tenant orchestration** — actor service has 29 orchestration XMLs: one or more per tenant. Other services largely use one XML per tenant.
- **Per-tenant initial-setup** — `flyway/sli/<service>/sql/<tenant>/` directories.
- **Per-tenant Kafka topics** — most topics end with `<tenant>` (e.g. `disburse_loan_api_mfi`). Producer prepends, consumer subscribes by prefix.

## Config sources (in order of precedence)

1. **Environment variables** — overrides everything; used in container deploys.
2. **`application-<profile>.properties`** in each service.
3. **`application.properties`** baseline.
4. **Master-data tables** (`mfi_masterdata.code_master_details`) — runtime configurable values like `${maker_checker_enabled}`, slab thresholds, calendar, etc. Cached in Redis DB 1.
5. **`@NovopayConfig`** annotation in `infra-masterdata` — declarative config injection.

## Drift to watch

[`../platform/config-drift-map.md`](../platform/config-drift-map.md) is the audit. Recurring patterns:

- Same property name with different defaults across services (e.g. timeouts, retry counts).
- Tenant-specific values that should be uniform (e.g. business hours).
- Config values referenced in orchestration XML (`${…}`) that the service forgot to register.

## Multinode batch coordination

[`../platform/multinode-batch.md`](../platform/multinode-batch.md) — HIGH RISK item:

- **No leader election** in the batch service. `AutoScheduler` runs on every instance.
- `BatchScheduleService.canStart(scheduleId)` is a non-atomic check against Spring Batch metadata.
- Two scheduler instances can both read "not running" and both fire the job → **double execution**.
- Mitigation today: deploy one batch instance per cluster (operationally enforced, not architecturally).

## Redis DB index allocation

Per `RedisDBConfig` enum in `infra-cache`:

| Index | Owner | Purpose |
|---|---|---|
| 0 (DEFAULT) | OTP / payments-finnone / superset tokens | shared default |
| 1 (MASTER_DATA) | masterdata service | code masters |
| 2 (NOTIFICATION) | notifications | templates |
| 3 (ACTOR) | actor | actor/employee/office cache |
| 5 (ACCOUNTING) | accounting | products, schemes, accounting rules, txn catalogue, asset criteria, internal accounts; also `dl<…>` disbursement dedup |
| (apiRateLimit) | api-gateway | Bucket4j rate-limit state |

> Cross-service Redis sharing exists for the `dl<…>` disbursement dedup key (LOS writes, accounting reads). Coordinate carefully — both teams need to know the key format.

## Server ports (typical dev defaults)

| Service | Port |
|---|---|
| LOS | 8013 |
| webapp dev | 4000 |
| reporting | 8888 (context `/reporting`) |
| (others) | configured per service in `application.properties` |

## Database

- All services on **PostgreSQL / YugabyteDB** (wire-compatible).
- Reporting points at `localhost:5433/yugabyte` in dev.
- Spring Batch meta-tables live in **target service's** datasource (typically `mfi_accounting`). The batch service's `mfi_batch.batch_job` is the registry, not the meta.

## Kafka

- Bootstrap server configured per `application.properties`.
- Consumer offset is broker-managed (no Zookeeper).
- No DLQ topology in the platform — failed consumes are caught + logged + retried via per-flow retry topics or in-memory loops.

## Logging + observability

- Structured JSON logs with `tenant`, `STAN`, `apiName` MDC fields.
- Audit ES index — `novopay.platform.es.audit.index.prefix` per tenant.
- Telemetry Kafka topics drained by audit service.
- For deep platform-lib internals on tenant context + MDC, see [`../platform/platform-lib.md`](../platform/platform-lib.md).

## When you'll touch this

- Adding a new config flag → add a row in `code_master_details`, reference via `@NovopayConfig` or `${…}` substitution, evict the relevant Redis key.
- Onboarding a new tenant → create per-tenant XML overrides (where needed), Flyway directories, Kafka topic names. Run initial-setup.
- Debugging "feature behaves differently in env X" → check config drift first: `application-<profile>.properties`, then masterdata, then env vars.
