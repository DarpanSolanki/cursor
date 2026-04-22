# novopay-platform-lib — Guide for agents

## Purpose

`novopay-platform-lib` is the **shared framework** for Novopay microservices: orchestration, HTTP API surface, caching, messaging, bank integration templates, and typed “infra-*” clients for cross-service calls. **Prefer extending or using these abstractions** over ad-hoc copies in a single service.

## Gradle subprojects (verified `./gradlew projects` at repo root)

Output includes (human-readable order):

`adapter-aadhaar-xsd`, `hierarchy-builder`, `infra-accounting`, `infra-actor`, `infra-approval`, `infra-authorization`, `infra-batch`, `infra-cache`, `infra-cache-gateway`, `infra-essentials-elasticsearch`, `infra-essentials-mysql`, `infra-http-client`, `infra-jtf`, `infra-masterdata`, `infra-matm-payswiff`, `infra-message-broker`, `infra-navigation`, `infra-notifications`, `infra-platform`, `infra-reporting`, `infra-rule-engine`, `infra-service-gateway`, `infra-service-security`, `infra-task`, `infra-transaction-ccavenue`, `infra-transaction-hdfc`, `infra-transaction-indusind`, `infra-transaction-interface`, `infra-transaction-internal-interface`, `infra-transaction-paytm`, `infra-transaction-veri5`, `util-platform`.

## Module map (behavioural)

| Module | Responsibility |
|--------|----------------|
| **infra-platform** | Core: `AbstractProcessor`, `@Processor`, `ExecutionContext`, validators (`mandatoryFieldValidator`, …), `NovopayFatalException` / `NovopayNonFatalException`, dynamic datasource/Flyway hooks (services exclude Spring Boot auto-config for JDBC/Flyway and rely on infra) |
| **infra-navigation** | **ServiceOrchestrator**, **RequestProcessorImpl**, validator/processor/audit/alert orchestrators, **OrchestrationXMLParser**, **CallInternalOrchestrationProcessor** (same-JVM internal orchestration with explicit txn), transaction segmentation |
| **infra-service-gateway** | **ServiceGatewayController** — `POST /api/{apiVersion}/{apiName}`; wires `RequestProcessor`, `JSONHelperForRequestResponse`, `SecurityManager` |
| **infra-jtf** | JSON Template Framework — maps ExecutionContext to bank JSON and parses responses |
| **infra-http-client** | Outbound HTTP to other services (`NovopayHttpAPIClient`, etc.) |
| **infra-cache** / **infra-cache-gateway** | `NovopayCacheClient` / `ICacheClient`, Redis DB index enums used by services |
| **infra-message-broker** | Kafka integration base classes, config binding to XML |
| **infra-batch** | Batch scaffolding shared with Spring Batch jobs |
| **infra-accounting** / **infra-actor** / … | Service-specific **client** DTOs and executors consumed by other services |
| **infra-transaction-*** | Partner-specific payment/bank execution (HDFC, IndusInd, CCAvenue, Paytm, Veri5, MATM Payswiff) |
| **infra-transaction-interface** | Shared transaction executor abstractions (encryption, REST JSON services) |
| **infra-transaction-internal-interface** | Internal transaction wiring |
| **util-platform** | Cross-cutting utilities |
| **infra-rule-engine** | Rules integration |
| **infra-masterdata** / **infra-approval** / **infra-authorization** / **infra-task** / **infra-notifications** / **infra-reporting** | Client libraries for those domains |
| **hierarchy-builder** | Hierarchy utilities |
| **adapter-aadhaar-xsd** | XSD adapter asset |

## Version skew (code-verified)

- **Services** (e.g. accounting-v2): Spring Boot **3.5.6** (`novopay-platform-accounting-v2/build.gradle`).
- **Infra lib modules** (e.g. infra-platform, infra-navigation): Spring Boot plugin **3.2.11** in their own `build.gradle` files.

Do not use Boot 3.5-only APIs inside `novopay-platform-lib` without upgrading those modules consistently.

## How services depend on it

- Each microservice `build.gradle` pulls selected `in.novopay:infra-*` artifacts (versions often from `novopay-platform-dependency-mgmt` or plugin BOM).
- Accounting-v2 **includes** the lib repo as a composite Gradle build (see `.cursor/architecture.md`).
- **Processors** in a service are Spring beans with `@Processor` scanned from classpath; orchestration XML references them by **bean name**.

## Framework conventions enforced

1. **Orchestration-first APIs** — validators + processors + controls in XML; generic HTTP controller in infra-service-gateway.
2. **ExecutionContext** — `put` vs `putLocal` (`.cursor/rules/execution-context-discipline.mdc`).
3. **Transactions** — implicit for typical POST body requests; explicit for internal orchestration and GET-style paths per navigation rules.
4. **Errors** — `ServiceOrchestrator` wraps fatal/non-fatal and builds response maps.
5. **Internal orchestration** — `CallInternalOrchestrationProcessor` repopulates context and calls `processRequest` with explicit transaction flag.

## Global injections & their file paths (code-verified)

These are **platform-lib** components that are auto-registered by Spring (via `@Configuration` / `@Component`) when services scan `in.novopay` packages. This is what the platform injects “globally” *inside a microservice JVM* (distinct from API-gateway servlet filters).

### HTTP entry + orchestration shell (always present for SOF services)

- **Generic service controller**: `novopay-platform-lib/infra-service-gateway/src/main/java/in/novopay/infra/essentials/controller/ServiceGatewayController.java`
- **Request dispatch**: `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/RequestProcessorImpl.java`
- **Flow executor**: `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ServiceOrchestrator.java`
- **Processor execution + txn boundaries + undo**: `novopay-platform-lib/infra-navigation/src/main/java/in/novopay/infra/navigation/orchestrator/ProcessorOrchestrator.java`

### Transaction boundary implementation (navigation)

- **Implicit boundary** uses Spring `@Transactional(REQUIRES_NEW ...)`: `ProcessorOrchestrator#executeProcessorsWithImplictTransactionCommitBoundary(...)` in `infra-navigation/.../ProcessorOrchestrator.java`
- **Explicit boundary** uses `PlatformTransactionManager` and nested `<Transaction>` blocks roll back and run txn-undo processors: `ProcessorOrchestrator#executeProcessorsWithExplicitTransactionCommitBoundary(...)` in the same file.

### HTTP client pool + monitoring (infra-http-client)

- **Apache HttpClient pool + SSL trust-all + keep-alive + idle eviction**: `novopay-platform-lib/infra-http-client/src/main/java/in/novopay/infra/api/client/NovopayApiClientConfig.java`
  - Provides beans: `CloseableHttpClient`, `PoolingHttpClientConnectionManager`, `ConnectionKeepAliveStrategy`, and a scheduled idle-connection monitor.

### Redis connection factories + cache managers (infra-cache)

- **Redis DB-index specific `LettuceConnectionFactory` beans** (`defaultRedisConnectionFactory`, `masterDataRedisConnectionFactory`, `notificationRedisConnectionFactory`, `actorRedisConnectionFactory`, `authorizationRedisConnectionFactory`, `accountingRedisConnectionFactory`, `taskRedisConnectionFactory`, `apiRateLimitRedisConnectionFactory`, `losRedisConnectionFactory`, ...):  
  `novopay-platform-lib/infra-cache/src/main/java/in/novopay/infra/cache/configuration/NovopayCacheConfiguration.java`

### JPA auditing (infra-platform)

- **Auditor provider** (defaults to current user id or `"1"`):  
  `novopay-platform-lib/infra-platform/src/main/java/in/novopay/infra/platform/entity/JpaAuditConfiguration.java`

### Async tenant propagation (infra-batch)

- **Tenant-aware async executor** (`@EnableAsync` + `ThreadPoolTaskExecutor` + `TenantAwareTaskDecorator`):  
  `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/config/AsyncConfig.java`
- **TaskDecorator** implementation:  
  `novopay-platform-lib/infra-batch/src/main/java/in/novopay/infra/batch/config/TenantAwareTaskDecorator.java`

### Elastic APM (infra-platform; conditional)

- **APM attach** on startup: `novopay-platform-lib/infra-platform/src/main/java/in/novopay/infra/platform/elasticapm/config/ElasticApmConfig.java`
- **HTTP filter** naming APM transactions: `novopay-platform-lib/infra-platform/src/main/java/in/novopay/infra/platform/elasticapm/filter/ElasticApmTransactionNameFilter.java`
- **Outbound HTTP interceptor** dropping trace headers for specific bank hosts: `novopay-platform-lib/infra-platform/src/main/java/in/novopay/infra/platform/elasticapm/filter/DropParentTraceHeadersInterceptor.java` (used by HTTP client stacks that register Apache interceptors; confirm call sites when enabling).

## Key Java entry classes (grep / open first)

- `in.novopay.infra.navigation.orchestrator.ServiceOrchestrator`
- `in.novopay.infra.navigation.processor.RequestProcessorImpl`
- `in.novopay.infra.essentials.controller.ServiceGatewayController`
- `in.novopay.infra.navigation.processor.CallInternalOrchestrationProcessor`
- `in.novopay.infra.platform.navigation.AbstractProcessor`

## Extending the platform

- **New API** in a service: add `Request` to orchestration XML, wire validators/processors, add JTF templates only if external JSON mapping is needed.
- **New processor**: class extends `AbstractProcessor`, `@Processor`, register in XML.
- **New cross-service client**: extend the appropriate `infra-*` module; keep DTOs backward compatible.
- **New bank partner**: new `infra-transaction-*` (often) + JTF templates under `deploy/application/templates/bankIntegrationRequest|Response/{partner}/`.

---

*Cross-reference: `trustt-platform-ai-codegen-artifacts-java/sli/code-documentations/infra/Infra-Platform-Library-Deep-Analysis.md` and `Infra-Navigation-Library-Deep-Analysis.md`.*
