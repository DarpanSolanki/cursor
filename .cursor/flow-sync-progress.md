# Flow Sync Progress Tracker
# Date: 2026-04-17

## Wave Status
Wave 0 — Pre-flight: **COMPLETE**
Wave 1 — Accounting complete flows: **COMPLETE** (2026-04-17)
Wave 2 — Service contracts + EC keys: **COMPLETE** (2026-04-17)
Wave 3 — LOS + Payments deep contracts: **COMPLETE** (2026-04-17)
Wave 4 — Batch + Actor + Masterdata: **COMPLETE** (2026-04-17)
Wave 5 — Knowledge graph + API catalogue: **COMPLETE** (2026-04-17)
Wave 6 — Gap mining + final update: **COMPLETE** (2026-04-17)
Wave 7 — Disbursement 100% audit revalidation: **COMPLETE** (2026-04-22)

## Findings Counter (cumulative)
New flows documented: Waves 1–4 + **Wave 5** graph/catalogue
New EC keys mapped: ~20+ in `execution-context-contracts.md`
New contracts verified: **1797** unique HTTP `apiName` (orchestration union) + **146** Kafka registry topics + **71** accounting batch configs
Contract mismatches found: **1+** (disburse sync payload field drift remains open: `entity_type`, plus missing `stan` correlation)
Contract drifts found: transport + producer patterns (Waves 2–5)
New APIs catalogued: **1797** HTTP names + **146** topics (Wave 5)
Wave 6 new gap IDs: **GAP-065..069** (5× Medium — observability, Kafka poll config, pipe envelope, retry/idempotency doc, money-path checklist)
Wave 7 re-opened/new disbursement audit gaps: **GAP-070..073** (sync-contract + consumer-guard + callback-map defects)

## Wave 5 scorecard (2026-04-17)
- **APIs catalogued:** **2014** tallies — **HTTP `apiName` union: 1797** | **Kafka topics (event-registry headings): 146** | **Accounting batch configs: 71** | **Scheduled (scheduler-registry + notes): ~15** rows in registry file
- **Knowledge graph nodes:** **29** explicit registry rows + **146** Kafka topic refs (event-registry) → **175** total catalogue nodes
- **Knowledge graph edges:** **16** representative cross-cutting edges (full HTTP fan-out = per-`apiName` × caller matrix — not expanded)
- **Contract health (representative edges):** **2** aligned | **11** drift | **2** mismatch | **1** unknown
- **Money paths traced:** **6** (disbursement, repayment, interest accrual, closure, bulk collection, reversal/manual JE)

## Wave 4 scorecard (2026-04-17)
- Batch jobs mapped: **71** + batch platform shell; cross-service map: `cross-service-transactions.md`

## Wave 3 scorecard (2026-04-17)
- LOS-to-Accounting: **23** blocks | Payments-to-Accounting: **7** blocks | **`entity_type`:** **OPEN**

## Files — Wave 5
- `.cursor/api-catalogue.md` — NEW
- `.cursor/knowledge-graph.md` — NEW
- `.cursor/knowledge-graph.mmd` — NEW
- `.cursor/flow-sync-progress.md`, `.cursor/changelog.md`

## Gap IDs (cumulative from prior waves)
- **GAP-062..069** — see `gaps-and-risks.md` (**GAP-065..069** = Wave 6)

---

## Wave 7 note — 2026-04-22

Wave 0–6 remain historically complete. During the deep disbursement audit pass, previously marked resolved disbursement sync assumptions were revalidated against current code and reopened where drift still exists (`gaps-and-risks.md` GAP-070..073).

## ALL WAVES COMPLETE — 2026-04-17 (historical)

Waves 0–6 closed. Final report and KB updates in `.cursor/changelog.md` (FLOW_SYNC_COMPLETE). Cross-service synthesis: `.cursor/knowledge-graph.md`, `.cursor/cross-service-transactions.md`, `.cursor/gaps-and-risks.md` (summary table + **GAP-065..069**).
