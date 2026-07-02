# 09 · Shared platform — `novopay-platform-lib`

> Every service depends on this lib. It owns: orchestration parsing & execution, Spring Batch step builders, the cache abstraction, the Kafka wiring, the gateway/internal-API client, the masterdata validator, and the framework-level audit emitter.
>
> **Deep narrative:** [`../platform/platform-lib.md`](../platform/platform-lib.md) — read for the full module-by-module breakdown.
> **Per-service brain doc:** [`../services/novopay-platform-lib.md`](../services/novopay-platform-lib.md).

## What every session must know

### 1. The orchestration runtime

```
HTTP request hits gateway
  ▼
gateway routes to target service via NovopayAPIClient (lib: infra-api-client)
  ▼
service: ServiceOrchestrator.executeProcessors(ctx, request, ...) (lib: infra-navigation)
  ▼
For each <Validator> → execute (lib-built validators or service custom)
For each <Processor> → applicationContext.getBean(processor.bean).process(ctx)
For each <Control>   → branch based on regex/condition
For each <API>       → NovopayInternalAPIClient.callInternalAPI(ctx, apiName, ...)
```

Key types:
- `ExecutionContext` — the shared map between processors. Per-Request EC contracts: [`../platform/execution-context-contracts.md`](../platform/execution-context-contracts.md).
- `AbstractProcessor` — base for every processor. Implements `process(ExecutionContext)`.
- `Request` — the parsed `<Request>` object (validators, processor list, undo list, txn-mgmt flag, http-method).
- `OrchestrationXMLParser` — loads + merges all XMLs at startup.

### 2. The internal API client

`NovopayInternalAPIClient.callInternalAPI(executionContext, apiName, version, jobName, connTimeout, sockTimeout, isInternal)` — the way services call each other. Routing uses tenant context + the api master.

`NovopayAPIClient.callAPI(...)` — the gateway-side variant.

`<API id="x" name="y" version="v1">` in orchestration XML compiles to `callInternalAPI("y", "v1", ...)`. The `id` is just a local label.

### 3. The cache client

`NovopayCacheClient` (interface `ICacheClient`) wraps Redis with tenant prefixing. `RedisDBConfig` enum specifies the DB index per service: `ACCOUNTING=5`, `ACTOR=3`, `MASTER_DATA=1`, `NOTIFICATION=2`, `DEFAULT=0`. Spring `@Cacheable` users get an `accountingCacheManager`-style factory.

Tenant prefix is added automatically — never hard-code raw Redis keys.

### 4. The Spring Batch step builder

`CustomCommonStepBuilder` (in `infra-batch`) shapes every batch step. `ParallelBatchJob` and `ParallelCommonBatchJob` give partitioning. `GenericListenerV3` is the standard skip/retry listener.

Pattern in every `*BatchConfigService`:
- `JOB_NAME = "<orchestration request name>"`
- `GRID_SIZE = 10` (typical) — partitioned threads
- Wires `*ItemReader` (`SynchronizedItemStreamReader`), `*ItemProcessor`, `*ItemWriter`
- Failure rows → `*FailureEntityMapper` → `batch_failure_audit`

### 5. The masterdata validator + util

`<Validator bean="masterDataValidator">` is from `infra-masterdata`. Programmatic access: `MasterDataUtil.getBulkMasterDataMapping(ctx, datatypeSubTypePairs)` returns a nested map `(dataType → (code → value))`. Backed by Redis cache (DB 1).

### 6. The audit emitter

Services don't `INSERT` into `audit_log`. They declare:

```xml
<Processor bean="createGeneralLedgerProcessor">
  <AuditData key="entity_type" value="GENERAL_LEDGER"/>
  <AuditData key="new_data" value="${new_data}"/>
</Processor>
```

The framework (`infra-audit`) hooks the processor execution and emits an audit event via Kafka → audit service. This is why every state change has an audit trail without explicit code in the processor.

### 7. The Kafka consumer interface

`NovopayMessageBrokerConsumer` (in `infra-kafka`) is the interface every consumer bean implements. Wiring: `MessageBroker.xml` maps a topic prefix to a bean name; the framework instantiates a Kafka consumer thread that calls `processConsumerRecord(record)`.

Producer side: services `@Autowired` a `KafkaTemplate`-like wrapper or use a service-specific producer bean (e.g. `AccountingKafkaProducer`).

### 8. Tenant context

`ThreadLocalContext.setTenant(PlatformTenant)` is the resolution mechanism. Set at:
- API gateway `InitialFilter` (per request)
- Batch service `DirectJobExecutor.run()` (per job)
- Kafka consumer (per record, before processing)

Every downstream call (DB, internal API, Kafka publish, Redis) reads from this context.

## Why this matters

When debugging a behaviour that "should work the same in every service":
1. Check if the lib version is consistent across services. (See [`../platform/dependency-map.md`](../platform/dependency-map.md) for version drift.)
2. Check the lib code if the issue is in orchestration / EC / cache / kafka / batch / masterdata / audit / tenant.
3. **Don't change lib without weighing impact.** Every service consumes it. See [`../rules/platform-lib.md`](../rules/platform-lib.md).

## Where to extend the lib safely

- A new validator type → `infra-masterdata` or new `<Validator>` bean implementation; register via Spring.
- A new orchestration construct → `infra-navigation`; add corresponding XML schema element + parser + executor handler. **Touches every service.**
- A new cache backend → `infra-cache`; keep `ICacheClient` contract.
- A new Kafka pattern (DLQ, retry topology) → `infra-kafka`; coordinate with all consumer beans.
