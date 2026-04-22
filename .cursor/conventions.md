# Codebase conventions (observed + mandated)

**Worked examples / glossary / FAQ**: `.cursor/docs/patterns-and-examples.md`, `anti-patterns.md`, `glossary.md`, `faq.md`, `testing-patterns.md`.

## Build and versions

- **Java 17**, **Gradle**, **Spring Boot 3.5.x** on services (confirm per `build.gradle`).
- **Spring Cloud 2023.0.1** (BOM in accounting-v2).
- **Infra libs** may lag service Boot version — verify before using newer Spring APIs in shared libs.

## Package and naming

- **Processors**: `*Processor` extends `AbstractProcessor`, annotated `@Processor` (`in.novopay.infra.platform.annotations.Processor`).
- **Services**: `*Service` for business logic; `*DAOService` for DB access layered on repositories.
- **Entities**: `*Entity`; repositories `*Repository` (Spring Data).
- **Constants / error codes**: centralized constants classes (e.g. `AccountingConstants`); **no magic error strings** in new code.

## Orchestration

- XML in `deploy/application/orchestration/*.xml`; `Request` has `name`, HTTP method, `explicitTxnMgmt` (or equivalent attribute), ordered `Validator` and `Processor` lists, `Control` branches.
- Bean names in XML match Spring bean names of processors/validators.

## Data access

- **Native queries** preferred for YugabyteDB (`nativeQuery = true`).
- **Soft delete**: `is_deleted = false` on reads; soft-delete on writes with audit columns.
- **Pagination** for large sets; avoid load-all in hot paths.

## Context and APIs

- **`putLocal`** for step-local data; **`put`** only when downstream processors need the key.
- **Inter-service results**: `putAPIResponse` / `getValueFromAPIResponse` where framework provides them.

## Multi-tenant

- `ThreadLocalContext.getTenant()` / `setTenant()` around Kafka consumers and scheduled jobs that touch tenant data.

## Testing

- `MockMvc` tests post to `/api/v1/{apiName}` with JSON body (`ApiTesting` pattern).
- Financial changes: prefer replay/idempotency tests and DB assertions (see disburse sanity scripts in `.cursor/rules`).

## Workspace hygiene

- **Service repos**: microservice folders are separate git roots (multi-repo).
- **Docs that must not live in service git**: workspace `docs/<service>/` per `docs-outside-service-repos.mdc`.
- **system_brain**: curated operational knowledge; update when behaviour verified.

## Tiered responses for incidents

- Always offer **L0** (hotfix) + **L1** (proper fix) minimum; optional L2/L3 (`.cursor/rules/architect-thinking.mdc` — Tiered solution approach).

## Quick verification commands (agents)

- **Orchestration Request count per file**:  
  `grep -c '<Request name=' novopay-platform-accounting-v2/deploy/application/orchestration/*.xml`
- **Find Kafka consumers in accounting**:  
  `rg "implements NovopayMessageBrokerConsumer" novopay-platform-accounting-v2/src/main/java`
- **Gradle projects (accounting + lib)**:  
  `cd novopay-platform-accounting-v2 && ./gradlew projects` and `cd novopay-platform-lib && ./gradlew projects`

---

*Align with `.cursorrules` and `.cursor/rules/concise-crisp-code.mdc` for style.*
