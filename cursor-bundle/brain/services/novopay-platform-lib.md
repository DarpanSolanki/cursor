# `novopay-platform-lib` — Shared infrastructure (the framework every service depends on)

> Multi-module Gradle library. Every service's `build.gradle` depends on a subset of these. Owns the orchestration parser, the navigation/processor framework, the gateway/internal-API client, the cache abstraction, the Kafka wiring, the master-data validator, the Spring Batch builder utilities, and the audit emit hooks.
>
> **Deep narrative:** [`../platform/platform-lib.md`](../platform/platform-lib.md) — read that for the full module-by-module breakdown.

## Identity

| Field | Value |
|---|---|
| Type | Gradle multi-module library |
| Repo | [`novopay-platform-lib/`](../../novopay-platform-lib/) |

## Modules (top-level)

| Module | Owns |
|---|---|
| `infra-platform` | Core platform framework — `ExecutionContext`, `AbstractProcessor`, `NovopayFatalException`, `NovopayNonFatalException`, `@Processor` annotation |
| `infra-navigation` | Orchestration XML parsing + execution: `OrchestrationXMLParser`, `ServiceOrchestrator`, `Request`, `<Validator>` / `<Processor>` / `<Control>` / `<API>` element handling |
| `infra-service-gateway` | `NovopayInternalAPIClient` — service-to-service HTTP via the gateway / direct routing, tenant propagation |
| `infra-cache` | `NovopayCacheClient`, `ICacheClient`, Redis DB index enum (`RedisDBConfig.ACCOUNTING = 5`, etc.), `accountingCacheManager` factory |
| `infra-kafka` | Kafka producer + `NovopayMessageBrokerConsumer` interface; backbone for every service's Kafka wiring |
| `infra-batch` | `CustomCommonStepBuilder`, `ParallelBatchJob`, `ParallelCommonBatchJob`, `GenericListenerV3` — used by every Spring Batch job in accounting/LOS/payments |
| `infra-masterdata` | `MasterDataUtil`, `@NovopayConfig` config loader, `masterDataValidator` bean |
| `infra-audit` | Framework-level `<AuditData>` emit; auto-writes to `audit_log` |
| `infra-api-client` | `NovopayAPIClient` — gateway-side routing (resolves apiName → service host) |
| `infra-tenant` | `ThreadLocalContext`, tenant resolution, `PlatformTenant` |

(Plus several smaller modules. See repo root for the full list of `infra-*` directories.)

## Why every session must know this

- The orchestration XMLs in every service are **executed** by `ServiceOrchestrator` in this lib. A bug in how a Request behaves can be in the lib, not the service.
- `ExecutionContext` is the conduit between processors. Every processor reads from / writes to it. Per-Request EC contracts are documented in [`../platform/execution-context-contracts.md`](../platform/execution-context-contracts.md).
- `<API id="…">` element in orchestration XML compiles to `NovopayInternalAPIClient.callInternalAPI(...)` — the lib decides routing/timeout/retry.
- `<Validator bean="masterDataValidator">` is the lib's canonical validator using `MasterDataUtil`.
- `CustomCommonStepBuilder` shapes how every Spring Batch step is built; understanding partitioning and listener wiring requires reading the lib.
- Redis DB indexes are central — see `RedisDBConfig` enum.
- `audit_log` writes are framework-emitted — services don't `INSERT` audit rows; the lib does.

## When you'll touch this

- A behaviour shared across services is wrong (e.g. tenant propagation drops a header) → likely lives in `infra-tenant` / `infra-service-gateway`.
- A new orchestration construct is needed (a new `<Control>` mode, a new `<Processor>` annotation contract) → `infra-navigation`.
- Performance issue across batches → `infra-batch`.
- Cache hit-rate issue or cache eviction inconsistency → `infra-cache`.

> **Do not modify lib without weighing impact.** Every service depends on it. See [`../platform/platform-lib.md`](../platform/platform-lib.md) and [`../rules/platform-lib.md`](../rules/platform-lib.md).
