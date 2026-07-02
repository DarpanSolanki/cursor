---
name: reference_dpi_feature_branch
description: "DPI/DPIC work — mandatory repo checkout matrix; why agents miss improvements on integration branch"
metadata:
  node_type: memory
  type: reference
---

## When the task mentions DPI, DPIC, delayed payment interest, dpiAccrual*, dpiBilling

**Before grepping code or trusting KG flow output**, verify checkout:

| Repo | Branch | Why |
|------|--------|-----|
| `novopay-platform-accounting-v2` | `feature/delayed_payment_interest` | All DPI batch/calc/booking/billing Java + orchestration |
| `novopay-platform-initial-setup` | `feature/delayed_payment_interest` | Flyway V000122 (`DPI_GO_LIVE_DATE` seed), api_master, GL seeds |
| `novopay-platform-webapp` | `feature/delayed_payment_interest` | Masterdata UI for go-live dates (if UI work) |

Then: `scripts/bin/kg-switch.sh` (KG watermark must match feature branch, not `mfi_integration_*`).

## Symptom: "agent did not find my DPI improvements"

Common causes (verified 2026-06-22):

1. **Branch drift** — accounting-v2 on release train (`mfi_integration_v3.3.1.x`) while DPI ships on `feature/delayed_payment_interest`. Grep/KG on integration branch returns stale or empty DPI paths.
2. **Brain CHANGELOG lag** — kg-flow rows exist through ~2026-06-18 (`f09221144`); perf + go-live commits after that may lack `| kg-flow |` rows until shipped → `kg cases dpiAccrualCalculation` omits them.
3. **WIP gate** — only webapp on feature branch, accounting on integration → mixed workspace.
4. **fetch-latest rule** — always `git fetch` + read `feature/delayed_payment_interest` tip before RCA on DPI.

## Key shipped deltas (feature branch tip — verify with `git log`)

- **Perf (~3h → minutes):** preload PRIN+INT dues per loan; pg_hint_plan IndexScan on hot `loan_due_details` queries (`895cfc9ef`, `430f01b3b`).
- **UD §5.4 Day Zero:** `DpiGoLiveResolver` — masterdata `DPI_GO_LIVE_DATE` per product code; accrual floor; null config = no floor (`518b7c11d`).
- **Setup still required for QA/prod:** NPA GL rule catalogue **1328** (`DPI_NPA_ACCRUAL`); go-live dates for all `dpi_applicable=YES` products; cache restart after masterdata.

## Agent entry

1. `kg orient dpiAccrualCalculation` (after kg-switch)
2. `cursor-bundle/brain/changelog/CHANGELOG.md` — filter `DPIC|DPI|dpi`
3. Orchestration: `loans_orc.xml` requests `dpiAccrualCalculation`, `dpiAccrualBooking`, `dpiBilling`
4. Local demo: `scripts/dpic/`, `Makefile dpic-phase*`
