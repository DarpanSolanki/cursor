# MASTER BRAIN SYNC — PLATFORM INTELLIGENCE LOADER

**Purpose:** Load complete platform knowledge into active context.  
**Run:** At start of any new session, or type **"brain sync"**.  
**Do NOT** run full repo scan again — knowledge is already built in `.cursor/` and `system_brain/`.

---

## PHASE 1 — LOAD COMPLETE BRAIN (silent, no chat output)

Read every file in this **exact order**:

### CORE KNOWLEDGE

1. `.cursor/onboarding.md`
2. `.cursor/architecture.md`
3. `.cursor/platform-lib.md`
4. `.cursor/accounting-flows.md`
5. `.cursor/event-registry.md`
6. `.cursor/service-contracts.md`
7. `.cursor/orchestration-map.md`
8. `.cursor/service-dependency-graph.md`
9. `.cursor/multinode-batch.md` (if exists)
10. `.cursor/scheduler-registry.md`
11. `.cursor/redis-key-registry.md`
12. `.cursor/config-drift-map.md`
13. `.cursor/dependency-map.md`
14. `.cursor/test-coverage-map.md`

### RISK & RECOVERY

15. `.cursor/gaps-and-risks.md`
16. `.cursor/runbooks.md`

### EDGE CASES (every file)

17. `system_brain/edge_cases/` — every `.md` file in this directory  
18. `system_brain/events/` — every `.md` file in this directory

### RULES & HISTORY

19. `.cursorrules`
20. `.cursor/changelog.md` (**last 50 lines only**)

---

## PHASE 2 — ACTIVE INTELLIGENCE (internalize)

### When an issue is reported

1. Identify **service** and **flow**.  
2. Load flow from `accounting-flows.md` or `orchestration-map.md`.  
3. Check `gaps-and-risks.md` for known gaps on that path.  
4. Check `event-registry.md` for produce/consume correctness.  
5. Check `redis-key-registry.md` for TTL / lock issues.  
6. Check `runbooks.md` for mitigations.  
7. Trace execution path with **class + path**.  
8. Pinpoint failure with **evidence**.  
9. Propose fix: root cause, location, solution, fix risk.

### When a feature is requested

1. `orchestration-map.md` — existing XML?  
2. `platform-lib.md` — existing abstraction?  
3. `service-dependency-graph.md` — touched services?  
4. `event-registry.md` — events exist?  
5. `gaps-and-risks.md` — High-risk overlap?  
6. Use **this codebase’s** patterns, not generic best practices.  
7. Flag new gaps before coding.  
8. Estimate blast radius.

### When debugging (RCA)

1. Entry: `ServiceGatewayController` or Kafka consumer.  
2. Trace orchestration processor chain.  
3. Lenses: swallow, idempotency, Redis TTL, retry, contract, txn boundary, async, batch re-entrancy, schema, auth, observability, dead code.  
4. Cross-reference `gaps-and-risks.md`.  
5. Output RCA: ENTRY POINT → FLOW PATH → FAILURE POINT → ROOT CAUSE → EVIDENCE → FIX → RISK → RELATED GAPS.

---

## PHASE 3 — CONFIRM (chat output)

After reading, output the **BRAIN SYNC COMPLETE** block (counts from loaded files).

---

## PHASE 4 — WEEKLY REFRESH (only when user types **"weekly sync"**)

1. Review `git log --since="7 days ago" --name-only`.  
2. For each changed file: update flows, gaps (RESOLVED/NEW), `event-registry.md`, `redis-key-registry.md`, `scheduler-registry.md` as needed.  
3. Append `changelog.md` entry: `WEEKLY_SYNC | files | gaps resolved | new gaps | knowledge files | Readiness`.  
4. Update `.cursorrules` AGENT SELF-KNOWLEDGE counts.  
5. Report **WEEKLY SYNC COMPLETE** summary.

---

## PHASE 5 — AUTO-UPDATE ON EVERY TASK

After **any** task, verify:

| Question | If YES → update |
|----------|-----------------|
| Accounting or platform-lib touched? | `accounting-flows.md` / `platform-lib.md` |
| Event added/changed? | `event-registry.md` |
| Gap resolved/introduced? | `gaps-and-risks.md` + `changelog.md` |
| Redis key/TTL changed? | `redis-key-registry.md` |
| Orchestration XML changed? | `orchestration-map.md` |
| Changelog updated? | `changelog.md` (append-only) |

If any YES and file not updated → **task not done**.

---

*Canonical location: `.cursor/MASTER-BRAIN-SYNC.md`*
