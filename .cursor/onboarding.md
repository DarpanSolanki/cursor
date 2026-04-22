# Agent Onboarding — Read This First Every Session

## On workspace open, read in this order:
1. `.cursor/architecture.md` — system map
2. `.cursor/gaps-and-risks.md` — active risks (never ignore High items)
3. `.cursor/onboarding.md` — this file
4. **When work crosses services, Kafka, Redis, or batch→HTTP:** **`.cursor/knowledge-graph.md`** (pick the **money path** + **Edge Registry** rows) and, for partial-failure analysis, **`.cursor/cross-service-transactions.md`**. Companion diagram: **`.cursor/knowledge-graph.mmd`**.

## Before touching accounting module, always check:
- `.cursor/knowledge-graph.md` — which **nodes/edges** and **money path** (disburse, repayment, bulk collection, etc.) are affected
- `.cursor/accounting-flows.md` — full flow map
- `.cursor/event-registry.md` — events this module produces/consumes
- `.cursor/gaps-and-risks.md` — any open High risk in accounting
- `.cursor/execution-context-contracts.md` — EC keys for the orchestration spine you edit

## Before touching platform-lib, always check:
- `.cursor/platform-lib.md` — what is exposed, what pattern to follow
- Impact on all 7 dependent services before changing any interface

## Before adding any new event:
- Check `.cursor/event-registry.md` — no duplicates, no orphan events
- Ensure consumer exists, ensure error handling exists on consumer side

## The 4 High Risk gaps to proactively warn about (verify current row in `gaps-and-risks.md` — some sync rows may be RESOLVED):
1. **LOS disbursement sync no-ops if `entity_type` missing** — `novopay-mfi-los/.../DisbursementSyncService.java` — **knowledge-graph** edges **E6–E7** (`los_lms_disbursement_sync`).
2. **Accounting ↔ LOS disburse sync contract** — `novopay-platform-accounting-v2/.../LmsMessageBrokerConsumer.java` + JTF `disburseLoan` templates; keep aligned with LOS consumer (**gaps** table + **event-registry** `los_lms_disbursement_sync`).
3. **Disbursement Redis in-flight key has no TTL (LOS producer)** — `novopay-mfi-los/.../DisburseLoanAPIUtil.java` — graph node **RD-DISB-LOS**.
4. **Disbursement Redis in-flight key has no TTL (Accounting consumer)** — `novopay-platform-accounting-v2/.../LmsMessageBrokerConsumer.java` — graph node **RD-DISB-ACC**.

*(See also High: `RedisCacheClient.flushDb()`, interest-accrual `client_reference_number`, proactive excess refund writer — `.cursor/gaps-and-risks.md`.)*

## Knowledge files and what each covers:
- **`knowledge-graph.md`** + **`knowledge-graph.mmd`** — services, topics, Redis/DB groups, **16** representative **edges**, **6** **money paths**, SPOFs, contract health summary (Flow Sync)
- **`api-catalogue.md`** — **1797** union `apiName` + **146** Kafka topics + batch/scheduler tallies
- **`cross-service-transactions.md`** — **10** multi-service transactions (compensation / reconciliation / monitoring)
- **`flow-sync-progress.md`** — Waves 0–6 status and scorecards
- **`execution-context-contracts.md`** — EC spine (`postTransaction`, `loanWriteoff`, disburse) + risk taxonomy
- `architecture.md` — full system, services, communication patterns
- `platform-lib.md` — framework internals, global injections, extension patterns
- `accounting-flows.md` — every accounting flow end-to-end, data model, constraints
- `event-registry.md` — all 146 events, producers, consumers, schemas
- `service-contracts.md` — all inter-service APIs and shared types
- `gaps-and-risks.md` — all gaps with file:line evidence and risk level
- `conventions.md` — coding patterns specific to this codebase
- `changelog.md` — append-only history of all changes
- **`AGENTS.md`** (workspace root) — human/agent guide: graph-first RCA, parallel research, fix checklist
