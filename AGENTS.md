# Agent guide — Novopay sliProd workspace

This file orients **any automated or human agent** using this folder. Same path on disk = same artifacts for every session. **Bootstrap alignment:** `.cursor/onboarding.md`, `.cursorrules` (session order), and `.cursor/rules/always-on.mdc` all require or recommend **`.cursor/knowledge-graph.md`** for money / multi-service work — use one mental model: **graph first**, then `system_brain/` + code.

## How to ask for a fix (quick)

Give **symptom + error code + one correlator** (`external_ref_number`, LAN, `stan`, …) + **env** + **service guess** if you can. For a fuller template (and how agents should handle thin prompts), see **`.cursor/rules/effective-prompts-and-issue-triage.mdc`**.

## Knowledge graph first (cross-service and “where does this hurt?”)

For anything that **crosses services**, **Kafka**, **Redis**, or **batch → HTTP**, start from **`.cursor/knowledge-graph.md`** (and **`.cursor/knowledge-graph.mmd`** for a compact view):

1. **Find the money path** (disbursement, repayment, accrual, closure, bulk collection, reversal) and list every **hop** (service → topic → consumer → DB).
2. **Walk each edge** in the Edge Registry: note **ALIGNED / DRIFT / MISMATCH** and any **GAP-*** reference.
3. **Cross-check** **`.cursor/cross-service-transactions.md`** for the same flow: **Compensation**, **Reconciliation**, **Monitoring** — fixes must not assume a saga that does not exist.
4. **Cross-check** **`.cursor/gaps-and-risks.md`** (summary table + narrative **GAP-*** ) so you do not “fix” one symptom while leaving a documented **High** (e.g. `entity_type`, Redis TTL, Kafka swallow) untouched.
5. **HTTP/Kafka inventory scale**: **`.cursor/api-catalogue.md`** (union `apiName` + topics); use it to grep **all** callers before contract changes.

The graph is the **system-level picture**; `system_brain/flows/` and processors are the **step-by-step** truth. Use both.

## Thorough research: when to spawn multiple agents

**Goal:** Shorter wall-clock discovery **without** split-brain edits. Full policy: **`.cursor/rules/multi-agent-spawning.mdc`**.

| Pattern | Spawn? | Typical split |
|--------|--------|----------------|
| Map callers / XML / topics across **many repos** | **Yes** (read-only) | One agent per **service** dir, or per **apiName** / topic prefix |
| RCA on **one** stuck loan / one error code | **No** (one thread) | Single narrative: logs → DB → orchestration → code |
| **Money / GL / posting / disbursement state** code change | **One implementer** | Others **read-only**: grep evidence, graph edges, gap list |
| Compare two **design options** | **Yes** | Isolated chats; **merge one** design after review |
| Doc-only / knowledge-base updates | **Yes** if disjoint files | e.g. one agent `system_brain/`, another `.cursor/event-registry.md` — avoid editing the **same** paragraph twice |

**Efficient spawn recipe**

1. **Lead agent** (or human) pastes: goal, **branch**, correlators, and **which knowledge-graph path** is in scope.
2. **Helper agents**: explicit **read-only** brief — “`novopay-mfi-los` only: all references to `X`” / “payments only: `collectionLoanRepayment` call sites” — return **paths + line refs**, no edits.
3. **Integrator** merges findings, runs **contract** checks (`api-contract-safety.mdc`), updates **one** set of files for the fix.

**Non-negotiable:** Do **not** assign two agents to **write** the same processor or orchestration `Request` without sequence control.

## Read first (by task)

1. **Money, accounting, disbursement, repayment, GL, reversals, batches**  
   Open `system_brain/system_overview.md`, then the matching file under `system_brain/flows/` or `system_brain/debugging/`. Check `system_brain/edge_cases/` if the symptom sounds familiar. **Then** align to **`.cursor/knowledge-graph.md`** money path + **`.cursor/gaps-and-risks.md`** for known landmines.

2. **Standards and non‑negotiables**  
   Workspace root `.cursorrules` (Java/XML) and `.cursor/rules/*.mdc` (always-on rules plus domain rules). **Architecture map**: `.cursor/architecture.md`, `.cursor/platform-lib.md`, `.cursor/accounting-flows.md`, `.cursor/service-contracts.md`, `.cursor/gaps-and-risks.md`, `.cursor/conventions.md`. **ExecutionContext contracts**: `.cursor/execution-context-contracts.md`. **Short refs**: `.cursor/docs/glossary.md`, `patterns-and-examples.md`, `anti-patterns.md`, `faq.md`. **Money-path runbooks**: `system_brain/flows/*.md` (index in `.cursor/architecture.md` §12). Do not ship contract-breaking API changes; see `api-contract-safety.mdc`.

3. **Accounting module specifics**  
   After brain orientation, use `.cursor/rules/accounting.mdc` when working in `novopay-platform-accounting-v2/` (module reference + sync section). Update that file when accounting behaviour changes.

4. **Framework and codegen documentation**  
   `.cursor/index.mdc` lists priority paths under `trustt-platform-ai-codegen-artifacts-java/` (orchestration, infra deep-dives, data dictionaries).

5. **Verify in code and data**  
   Orchestration XML, processors, services, and DB/logs remain authoritative. The brain is a map, not a spec.

6. **Multiple agents in parallel**  
   Prefer **parallel read-only** partitions (per service / per topic) for broad scans; **serialize** implementation on money paths. See **`.cursor/rules/multi-agent-spawning.mdc`**.

## Fixing an issue: think from all angles (checklist)

Before you change code or config, walk this list (order is flexible; skip only what is clearly N/A):

1. **Graph & flow** — Which **nodes and edges** in `knowledge-graph.md` does this touch? Downstream **Kafka topic**, **Redis key group**, **DB schema**?
2. **Contracts** — HTTP **JTF / `apiName`**, Kafka **payload keys**, **ExecutionContext** keys (`.cursor/execution-context-contracts.md`). Changes **additive-only** unless explicitly approved (`api-contract-safety.mdc`).
3. **Gaps** — Does `.cursor/gaps-and-risks.md` already list this area (**GAP-***)? Fixing one layer without the paired service (e.g. `entity_type` producer **and** LOS consumer) can **silently** fail.
4. **Idempotency & retries** — `client_reference_number`, Redis guards, consumer replay, `@Retryable` + non-idempotent callee (`cross-service-transactions.md`, **GAP-068**-style patterns).
5. **Partial failure** — No automatic **compensation** across HTTP; what **reconciliation** or **ops** path picks up the pieces?
6. **Observability** — Can you trace with **`stan`** / tenant / business key across hops (**GAP-066**)? Entry/exit logs, failure persistence, alerts?
7. **Blast radius** — **`novopay-platform-lib`** change → all dependent services (`.cursorrules` P1). **Event** add/change → `.cursor/event-registry.md`.
8. **Knowledge sync** — If behaviour or risk changed: `.cursor/changelog.md` append; update gaps/registry/accounting docs per `.cursorrules` checklist.

## Where things live

| Area | Location |
|------|----------|
| **System-level flow graph (money paths, edges, SPOFs)** | `.cursor/knowledge-graph.md`, `.cursor/knowledge-graph.mmd` |
| Curated flow/runbook notes | `system_brain/` |
| Cursor agent rules | `.cursor/rules/*.mdc` |
| Cross-cutting workspace docs (not in service repos) | `docs/` (see `docs-outside-service-repos.mdc`, including workspace `docs/` maintenance section) |
| Microservice source | `novopay-platform-*/`, `novopay-mfi-los/`, … |

## Session handoff

When pausing or switching agents, record: **goal**, **done/blocked**, **exact service paths and branch**, **evidence** (error codes, correlators—no secrets), and **open risks** (contract, idempotency, DB). See **`always-on.mdc`** (Workspace brain + rules / session handoff) for the full checklist.

## Editing `system_brain/`

Follow **`always-on.mdc`** (system_brain maintenance section: factual notes, links to code, no secrets). Add new **`.mdc` rules** to **`system_brain/rules/rule_inventory.md`**.

## Git note

**Multi-repo**: run `git` in the correct **`novopay-platform-*` / `novopay-mfi-los`** directory, not necessarily the workspace root.

`system_brain/` is **workspace working memory**. Optional root `.gitignore`: uncomment `system_brain/` only if the team wants it excluded when the workspace root is tracked.
