<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.md only routes here. -->

# Tiered solution approach

When working on **any** bug, production issue, JIRA, or enhancement — always present solutions in tiers. The goal: **reduce TAT** with an immediate fix, then show the architectural path forward.

## Always present these tiers

### L0 — Hotfix / immediate (minutes–hours, no schema change, no lib upgrade)
- Smallest code change that fixes the symptom **safely**.
- Config change, flag toggle, condition fix, null guard, status check.
- No new dependencies, no schema migration, no new API.
- **Deploy**: Same build, same branch, minimal testing.
- **Use when**: Production is broken NOW and users are affected.

### L1 — Proper fix (hours–1 day, same framework, same schema)
- Correct root cause within existing code and framework.
- Refactor the logic, add missing validation, fix the query, handle the edge case properly.
- May add new methods, processors, or service changes — but no schema or lib changes.
- **Deploy**: Normal release cycle, standard QA.
- **Use when**: Root cause is a code-level flaw that L0 only bandaids.

### L2 — Enhancement (1–3 days, may involve schema change or new config)
- Better design: add a DB column, new index, new Kafka topic, new config property.
- Refactor flow for correctness (e.g. add idempotency key column, add status tracking, add audit column).
- May require Flyway migration, config deployment, cache eviction.
- **Deploy**: Planned release, schema migration, regression testing.
- **Use when**: The current design has a structural gap that L1 cannot fully address.

### L3 — Architectural improvement (days–weeks, framework/lib upgrade, cross-module)
- Upgrade a library or framework version (e.g. Spring Boot 3.x features, Java 21 virtual threads, reactive WebClient).
- Introduce a new pattern (circuit breaker, outbox pattern, event sourcing, CQRS).
- Cross-module refactor (shared lib change, new inter-service contract, new Kafka event).
- External tool/service adoption (distributed tracing, schema registry, API gateway policy).
- **Deploy**: Major release, cross-team coordination, extensive testing.
- **Use when**: The problem is systemic and will keep recurring without a design-level change.

## How to present

```
## L0 — Hotfix (deploy today)
[What to change, where, why it's safe, what it doesn't fix]

## L1 — Proper fix (next sprint)
[Root cause fix, what changes, why it's better than L0]

## L2 — Enhancement (planned)
[Schema/config/flow change, what it enables, migration steps]

## L3 — Architectural (roadmap)
[Framework/pattern/tool, what problem it solves at scale, rough effort]
```

## Rules

- **After every analysis / RCA / Jira triage / “what’s next?”**: emit a full **OPTIONS BOARD** — **L0 + L1 + L2 + L3** — before recommending a single next step. Planning engine enforces this via autopilot + `00-workspace-core.mdc`.
- **Always start with L0**. Even if the real fix is L2, the team needs something deployable NOW for production fires.
- **L2 and L3 are not optional after analysis** — if a tier does not apply, write `N/A — <one line why>`, do not omit the row.
- **Include code-fix options when they exist** — do not bury L1/L2 behind “gather more evidence” when the hotspot is already visible in code.
- Evidence/prod checks may be a **prerequisite under a tier**, never a substitute for the board.
- **Be honest about trade-offs**: L0 may leave tech debt. Say so. L3 may take weeks. Say so.
- **Tag effort and risk**: For each level, indicate approximate effort (hours/days) and deployment risk (low/medium/high).
- **Don't over-engineer L0**: The point is speed. A perfect L0 that takes 3 days defeats the purpose.
- **Don't under-think L1**: If L0 is deployed, L1 must actually fix the root cause, not just be a slightly better bandaid.

## Examples from this codebase

### 3x NEFT duplicate
- **L0**: Add status check in consumer — skip if loan is ACTIVE. (30 min, no schema change)
- **L1**: Fix NEFT lookup to include both NEF and NEI; fix else-branch to set DO_TRANSACTION=false; update disbursement_status after NEF. (half day)
- **L2**: Add `idempotency_key` column to transaction table; check before any bank call. Add Redis distributed lock with TTL. (1-2 days, schema change)
- **L3**: Adopt outbox pattern — write bank call intent to DB first, then a poller/consumer picks it up exactly-once. Eliminates duplicate at the architecture level. (1-2 weeks)

### Negative net disbursement (-501)
- **L0**: Add `net_disbursed_amount >= 0` validation before bank call — fail-fast with clear error. (30 min)
- **L1**: Fix formula to use `approved_amount` instead of `loan_amount`; fix PROC_FEE config so charges don't exceed approved amount. (half day)
- **L2**: Add DB constraint `CHECK (net_disbursed_amount >= 0)`; add charge validation at configuration time (charge amount < max approved amount). (1 day, schema + config)
- **L3**: Introduce a `DisbursementAmountCalculator` service with comprehensive unit tests; extract all financial formulas into a testable, auditable calculation engine. (3-5 days)

### LOS KFS broke on empty charges_details
- **L0**: Restore placeholder in `charges_details` when no charges configured. (30 min)
- **L1**: Add `charges_configured` flag so callers can distinguish no-config from real data. Keep placeholder for backward compat. (1-2 hours)
- **L2**: Version the API response (v1 keeps placeholder, v2 returns clean empty list + flag). Migrate callers one by one. (2-3 days)
- **L3**: Adopt API contract testing (consumer-driven contracts) so response shape changes are caught before merge. (1-2 weeks, tooling)

## When to suggest external tools/libs (L3 ideas)

Mention these when the problem pattern fits — even if adoption is months away, naming the concept helps learning:

| Problem pattern | Tool/concept to mention |
|----------------|----------------------|
| Duplicate processing | Outbox pattern, exactly-once Kafka semantics, idempotency key |
| Cascading failures across services | Circuit breaker (Resilience4j), bulkhead pattern |
| Hard to trace cross-service flows | Distributed tracing (Micrometer + Zipkin/Jaeger), correlation ID |
| API contract breaks | Consumer-driven contract testing (Pact), schema registry |
| Slow batch jobs | Java 21 virtual threads, parallel streams, Spring Batch partitioning |
| Schema migration pain | Flyway versioned migrations, expand-contract pattern |
| Config drift across envs | Spring Cloud Config, feature flags (Unleash/LaunchDarkly) |
| Cache inconsistency | Cache-aside with TTL, write-through, Redis pub/sub invalidation |
| Monitoring blind spots | Structured logging (JSON), metrics (Micrometer), alerting (Prometheus + Grafana) |

**Keep L3 suggestions to 1-2 lines.** The goal is to plant the seed and name the concept — not write a proposal.

---

