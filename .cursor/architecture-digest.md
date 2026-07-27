GENERATED FILE — edit architecture.md, never this digest.

# Architecture digest (session bootstrap)

SoT: `.cursor/architecture.md`. Escalate to full file for deep service maps, full diagrams, or any section not listed below.

# sliProd — System architecture map

**Scope**: Workspace layout as checked in this repo (multi-repo folders under one root). **Authoritative runtime behaviour**: orchestration XML + processors + DB + logs; this file orients agents quickly.


## 0. Build topology (verified)

- **`novopay-platform-accounting-v2`** uses a **Gradle composite / included build** for **`novopay-platform-lib`** (output of `./gradlew projects` in accounting-v2: *Included builds → `:novopay-platform-lib`*).
- **`novopay-platform-lib`** root `./gradlew projects` lists **32 subprojects** (infra-*, util-platform, hierarchy-builder, adapter-aadhaar-xsd) — use that command after dependency or module changes.


## 1. Microservices and boundaries

| Directory | Role | Typical data store | Entry style |
|-----------|------|-------------------|-------------|
| `novopay-platform-api-gateway` | Single HTTP entry for clients; auth, session, rate limit, STAN dedupe, forwards to backends | Gateway DB (sessions, clients, STAN, forward URLs) | REST → `NovopayAPIClient` / internal calls |
| `novopay-platform-accounting-v2` | LMS core: loan accounts, disbursement/repayment, GL/posting, EOD batches, SI/eNACH, insurance/DCF paths | `mfi_accounting` (Yugabyte) schema typical | REST `/api/{version}/{apiName}` via **infra-service-gateway** + Spring Batch + Kafka consumers |
| `novopay-mfi-los` | Loan origination, applications, disbursement producer, sync consumers | LOS schema | REST + Kafka |
| `novopay-platform-actor` | Customers, employees, meetings, KYC-adjacent data | Actor schema | REST / orchestration |
| `novopay-platform-payments` | Collections rails, schedules, payment integrations | Payments schema | REST + callbacks via gateway |
| `novopay-platform-task` | Workflow tasks | Task schema | REST |
| `novopay-platform-masterdata-management` | Master data, **business date** (`updateBusinessDate`) | Masterdata schema | REST + batch |
| `novopay-platform-authorization` | Roles / usecases / permissions | AuthZ schema | REST |
| `novopay-platform-approval` | Maker-checker drafts | Approval schema | REST |
| `novopay-platform-audit` | Audit trail consumption | Audit schema | Kafka + REST |
… (table truncated — see full architecture.md) …

**Not in this list**: `aicodegen/`, `trustt-platform-ai-codegen-artifacts/` — documentation and codegen artifacts, not runtime services.


## 2. Accounting-v2 Spring Boot shell (verified)

```30:37:trustt-platform-accounting/src/main/java/in/novopay/accounting/Application.java
@SpringBootApplication
@EnableAutoConfiguration(exclude = { DataSourceAutoConfiguration.class, FlywayAutoConfiguration.class })
@ComponentScan(basePackages = "in.novopay")
@EnableCaching
@EnableRetry
@EnableJpaRepositories(basePackages = {"in.novopay.*"})
@EntityScan(basePackages = {"in.novopay.*"})
```

- **DataSource and Flyway** are intentionally **not** auto-configured here; **infra-platform** owns dynamic datasource / migration setup (see class Javadoc in same file).


## 3. Orchestration surface area — accounting-v2 (verified counts)

`grep -c '<Request name=' deploy/application/orchestration/*.xml` in **accounting-v2**:

| File | `<Request name=` count |
|------|------------------------:|
| `ServiceOrchestrationXML.xml` | 138 |
| `loans_orc.xml` | 82 |
| `mfi_orc.xml` | 59 |
| `loans_insurance_orc.xml` | 26 |
| `group_mfi_orc.xml` | 19 |
| `product_transaction_orc.xml` | 12 |
| `product_transaction_accounting_definition_orc.xml` | 12 |
| `insurance_orc.xml` | 12 |
| `loans_notification.xml` | 2 |

**Implication**: API discovery by “read one file” is insufficient; use `grep '<Request name='` when mapping entrypoints.


## 4. Shared platform libraries (`novopay-platform-lib/`)

Gradle composite modules (see `settings.gradle`):

- **infra-platform**: `AbstractProcessor`, validators, annotations, exceptions, tenant/thread context. **Spring Boot plugin: 3.2.11** (see `infra-platform/build.gradle`).
- **infra-navigation**: `ServiceOrchestrator`, `RequestProcessor`, orchestration XML parsing, transaction boundary behaviour, `CallInternalOrchestrationProcessor`. **Spring Boot plugin: 3.2.11** (see `infra-navigation/build.gradle`).
- **infra-service-gateway**: `ServiceGatewayController` — `POST /api/{apiVersion}/{apiName}` → `RequestProcessorImpl` → orchestration.
- **infra-jtf**: JSON Template Framework for bank/integration request–response mapping.
- **infra-http-client**: `NovopayHttpAPIClient`, internal HTTP client patterns.
- **infra-cache** / **infra-cache-gateway**: Redis clients, DB index conventions per service.
- **infra-message-broker**: Kafka producer/consumer abstractions (`NovopayMessageBrokerConsumer`, etc.).
- **infra-batch**: Spring Batch integration helpers.
- **Domain client libs**: `infra-accounting`, `infra-actor`, `infra-authorization`, `infra-task`, `infra-masterdata`, `infra-approval`, `infra-notifications`, `infra-reporting`.
- **Bank / payment**: `infra-transaction-hdfc`, `indusind`, `ccavenue`, `paytm`, `veri5`, `matm-payswiff`, `infra-transaction-interface`, `infra-transaction-internal-interface`.
- **Other**: `util-platform`, `hierarchy-builder`, `infra-rule-engine`, `infra-essentials-mysql`, `infra-essentials-elasticsearch`, `infra-service-security`, `adapter-aadhaar-xsd`.

Services depend on these as Gradle dependencies; **do not duplicate** framework concerns in service code.


## 5. Inter-service communication patterns

1. **Synchronous HTTP**
   - External clients → **API Gateway** → backend service HTTP (resolved by apiName / service registry / config).
   - Service-to-service: `NovopayInternalAPIClient` / `NovopayHttpInternalAPIClient` (orchestration-driven) — **separate transaction** from caller.

2. **Same JVM “internal API”**
   - `CallInternalOrchestrationProcessor` builds a new `ExecutionContext` and runs another Request with **explicit** transaction management — still not a shared DB transaction with the outer flow.

3. **Kafka**
   - Tenant-suffixed topics. **Accounting broker config**: `trustt-platform-accounting/deploy/application/messagebroker/MessageBroker.xml` (see `.cursor/service-contracts.md` for beans). Broader contracts: `system_brain/events/kafka_topics.md`.

4. **No gRPC** observed as the primary pattern in this workspace; the spine is REST + Kafka + batch.

<!-- architecture-digest max=8000 -->
