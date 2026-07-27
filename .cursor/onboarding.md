# Agent Onboarding — Read This First Every Session

## On workspace open, read in this order:
1. `.cursor/onboarding.md` — this file
2. `.cursor/gaps-and-risks-digest.md` — open High rows + Medium/Low index. **Escalate** to full `.cursor/gaps-and-risks.md` only when a GAP-id/area is flagged, Medium/Low narrative is needed, or the digest is missing/stale
3. `.cursor/architecture-digest.md` — escalate to full `.cursor/architecture.md` for deep service maps / diagrams, or if the digest is missing/stale
4. **When work crosses services, Kafka, Redis, or batch→HTTP:** prefer **KG MCP** (`trustt-kg`) first; then **`.cursor/knowledge-graph.md`** (money path + Edge Registry) and **`.cursor/cross-service-transactions.md`**. Companion diagram: **`.cursor/knowledge-graph.mmd`**.

## Before touching accounting module, always check:
- `.cursor/gaps-and-risks-digest.md` — any open High risk in accounting (escalate to full gaps SoT when flagged)
- `.cursor/knowledge-graph.md` — which **nodes/edges** and **money path** (disburse, repayment, bulk collection, etc.) are affected
- `.cursor/accounting-flows.md` — full flow map
- `.cursor/event-registry.md` — events this module produces/consumes
- `.cursor/execution-context-contracts.md` — EC keys for the orchestration spine you edit

## Before touching platform-lib, always check:
- `.cursor/platform-lib.md` — what is exposed, what pattern to follow
- Impact on all 7 dependent services before changing any interface

## Before adding any new event:
- Check `.cursor/event-registry.md` — no duplicates, no orphan events
- Ensure consumer exists, ensure error handling exists on consumer side

## The 4 High Risk gaps to proactively warn about (verify current row in `gaps-and-risks-digest.md` — escalate to full SoT; some sync rows may be RESOLVED):
1. **LOS disbursement sync no-ops if `entity_type` missing** — LOS `DisbursementSyncService.java` — **knowledge-graph** edges **E6–E7** (`los_lms_disbursement_sync`).
2. **Accounting ↔ LOS disburse sync contract** — Accounting `LmsMessageBrokerConsumer.java` + JTF `disburseLoan` templates; keep aligned with LOS consumer (**gaps** table + **event-registry** `los_lms_disbursement_sync`).
3. **Disbursement Redis in-flight key has no TTL (LOS producer)** — LOS `DisburseLoanAPIUtil.java` — graph node **RD-DISB-LOS**.
4. **Disbursement Redis in-flight key has no TTL (Accounting consumer)** — Accounting `LmsMessageBrokerConsumer.java` — graph node **RD-DISB-ACC**.

*(See also High: `RedisCacheClient.flushDb()`, interest-accrual `client_reference_number`, proactive excess refund writer — digest / full gaps SoT.)*

## Knowledge files and what each covers:
- **`gaps-and-risks-digest.md`** / **`architecture-digest.md`** — session bootstrap (escalate to full SoT when needed)
- **`knowledge-graph.md`** + **`knowledge-graph.mmd`** — services, topics, Redis/DB groups, **16** representative **edges**, **6** **money paths**, SPOFs, contract health summary (Flow Sync)
- **`api-catalogue.md`** — **1797** union `apiName` + **146** Kafka topics + batch/scheduler tallies
- **`cross-service-transactions.md`** — **10** multi-service transactions (compensation / reconciliation / monitoring)
- **`flow-sync-progress.md`** — Waves 0–6 status and scorecards
- **`execution-context-contracts.md`** — EC spine (`postTransaction`, `loanWriteoff`, disburse) + risk taxonomy
- `architecture.md` — full system, services, communication patterns (via digest first)
- `platform-lib.md` — framework internals, global injections, extension patterns
- `accounting-flows.md` — every accounting flow end-to-end, data model, constraints
- `event-registry.md` — all 146 events, producers, consumers, schemas
- `service-contracts.md` — all inter-service APIs and shared types
- `gaps-and-risks.md` — full gaps SoT with file:line evidence (via digest first)
- `conventions.md` — coding patterns specific to this codebase
- `changelog.md` — append-only history of all changes
- **`AGENTS.md`** (workspace root) — human/agent guide: graph-first RCA, parallel research, fix checklist

## Test / ship selection (GAP-G)

- **Canonical runner:** `bash scripts/bin/ntest.sh …` (wraps `scripts/testing/ntest.py`)
- **Impact plan:** `python3 scripts/lib/impact_tests.py --banner` — prints tier + planned wall (serial-suite estimate)
- **Money paths:** FIX-PLAN gate + universal invariants always on; never skip invariants to go faster
- **Speed doctrine:** select fewer cases (direct full / sibling smoke / dcf representatives) — never weaken money rails
- **LAN taxonomy:** SHG has children; JLG/INDL do not — flowtest refuses wrong fixture shape
- **Penal:** `scope=out` — not in coverage denominator (wont-do)
