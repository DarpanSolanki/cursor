# DPI test coverage map (workspace harness)

**Canonical runner:** `ntest run dpic.extended_regression`  
**QA batch path:** `ntest api accounting <job> --batch --job-time <ms>` + `wait_batch_job.sh` → `COMPLETED`  
**Three-job proof:** `bash scripts/dpic/run_dpi_three_job_verify.sh` · `ntest run dpic.three_job_verify`  
**June slice proof:** `bash scripts/bin/dpi-june-slice-proof.sh` · `ntest run dpic.june_slice_job_proof`

## QA invocation (mandatory — no simulated accrual writes)

```bash
# 1) Fixture hygiene (before any scenario class on canonical LANs)
bash scripts/dpic/reset_dpi_fixtures.sh

# 2) Ensure accounting
bash scripts/bin/novopay-service.sh ensure accounting --compile

# 3) Fire batch jobs exactly like QA (gateway batch API — not curl stubs, not accrual INSERTs)
JOB_TIME=1782563400000 bash scripts/bin/ntest.sh api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME"
bash scripts/dpic/lib/wait_batch_job.sh dpiAccrualCalculation "$JOB_TIME" "$(date +%s)"

JOB_TIME=1782563400000 bash scripts/bin/ntest.sh api accounting dpiAccrualBooking --batch --job-time "$JOB_TIME"
bash scripts/dpic/lib/wait_batch_job.sh dpiAccrualBooking "$JOB_TIME" "$(date +%s)"

JOB_TIME=1782563400000 bash scripts/bin/ntest.sh api accounting dpiBilling --batch --job-time "$JOB_TIME"
bash scripts/dpic/lib/wait_batch_job.sh dpiBilling "$JOB_TIME" "$(date +%s)"

# Registry equivalents (same HTTP path; ntest runs wait_batch_job.sh when wait_batch: true)
ntest run batch.dpi_calc
ntest run batch.dpi_booking
ntest run batch.dpi_billing

# Full reset → daily calc/booking loop → billing → slice SQL (8060160)
ntest run dpic.three_job_verify
```

**`wait_batch` in registry:** `batch.dpi_*` set `wait_batch: true` — `ntest run` polls `mfi_batch.batch_job_execution` until `COMPLETED` via `scripts/dpic/lib/wait_batch_job.sh` (interim QA mirror until native `batch_completed` assertion lands).

**`SEED_CALC_WINDOW`:** default `0` on `run_eod_dpi_only.sh` / `run_eod.sh`. Value `1` runs `seed_calc_window.sql` (documented bypass INSERT — not for passing tests).

## Column audit gate (post-batch, mandatory)

After real `ntest` batch jobs (`COMPLETED`), run:

```bash
bash scripts/dpic/lib/run_dpi_column_audit.sh <loan_account_id> <business_date>
# wired into run_dpi_three_job_verify.sh after calc/booking/billing
```

| SQL | Checks |
|-----|--------|
| `verify_dpi_accrual_slice_integrity.sql` | start/end dates, contiguity, month-end/due seals, grace-overlap micro-slice (SDCP-11030), posting anchors |
| `verify_dpi_booking_billing_audit.sql` | `transaction_master` amount/value-date vs slice; GL legs balanced (C/D); billed accrual vs `loan_due_details` DPI |

Canonical LANs: `8060160` (standard 3-job), `8057160` (grace overlap), `116360` (SHG parity). **0 violations** required before ship.

## Fixture LANs (`lib/dpi_fixture_constants.sh`)

| Role | loan_account_id | LAN | Used by |
|------|-----------------|-----|---------|
| Standard regression | `8060160` | `6004044425` | posting calendar, EOD txn, billing UD, APIs |
| Grace / overlap / two-EMI | `8057160` | `6004041325` | grace E2E, overlap, two_emi, multi-EMI |
| SHG parent parity | `116360` | `6000001074` | SDCP-11012 parent=sum(children) |
| Child JLG repayment | `8048470` | `6004029335` | childLoanRepayment DPI |

**Why 8057160/116360 were empty:** `purge_local_dpi_all.sql` + setup SQL clears `dpi_accrual_details` but accruals are only recreated by **`dpiAccrualCalculation`** — scripts that asserted without calling the batch job saw zero rows.

## Canonical local job invocation (QA-shaped)

```bash
# Ensure accounting + compile if Java changed
bash scripts/bin/novopay-service.sh ensure accounting --compile
bash scripts/bin/agent-ops.sh before-test dpiAccrualCalculation

# Single batch job (preferred — registry type:batch)
ntest run batch.dpi_calc          # dpiAccrualCalculation
ntest run batch.dpi_booking       # dpiAccrualBooking
ntest run batch.dpi_billing       # dpiBilling

# Ad-hoc with explicit job_time (18:00 IST ms)
JOB_TIME=1782563400000 ntest api accounting dpiAccrualCalculation --batch --job-time "$JOB_TIME"
bash scripts/dpic/lib/wait_batch_job.sh dpiAccrualCalculation "$JOB_TIME" "$(date +%s)"

# Full EOD chain (fixture LAN)
LOAN_ACCOUNT_ID=8060160 bash scripts/dpic/run_eod_dpi_only.sh

# From shell helpers (purge + ntest + wait)
source scripts/dpic/lib/dpi_demo_fixture.sh
dpi_call_batch dpiAccrualCalculation "$JOB_TIME"
dpi_call_eod_chain "$JOB_TIME"   # calc → booking → billing
```

Poll completion: `scripts/dpic/lib/wait_batch_job.sh <jobName> <job_time_ms> <run_started_epoch>`  
Batch status: `mfi_batch.batch_job_execution` where `status=COMPLETED`.

## Audit: insert-only vs job-first

| Path | Classification | Notes |
|------|----------------|-------|
| `run_grace_*`, `run_multi_emi_*`, `run_dpi_two_emi_*`, `run_dpi_shg_*` | ✅ Real jobs | setup SQL then `dpiAccrualCalculation` + `wait_batch_job` |
| `run_dpi_posting_calendar_regression.sh` | ✅ Real jobs | daily calc+booking loop + billing |
| `run_dpi_eod_txn_regression.sh` | ✅ Real jobs | calc → month-end booking → billing |
| `run_eod_dpi_only.sh` | ✅ Real jobs | `SEED_CALC_WINDOW=0` default; ntest batch chain |
| `run_dpi_three_job_verify.sh` | ✅ Real jobs | reset → setup SQL → ntest calc/booking loop + billing |
| `run_dpi_post_eod_verify.sh` | ⚠️ Assert only | requires prior job run |
| `seed_calc_window.sql` | ❌ Bypass | zero-amount anchor INSERT — opt-in `SEED_CALC_WINDOW=1` |
| `seed_dpi_accrual_history_bloat.sql` | ❌ Bypass | perf fixture only (`run_dpi_batch_perf_e2e.sh`) |
| `run_eod.sh` | ⚠️ Hybrid | curl batch APIs; `SEED_CALC_WINDOW=0` default |

**Demo loan:** `8060160` / `6004044425` · **job_time:** `1782563400000`

**Out of scope (per QA plan):** `generateDPIPresentationFiles` quartet, `loanWriteoff`.

## Covered (registry / scripts)

| Surface | Registry / script | DPI role |
|---------|-------------------|----------|
| dpiAccrualCalculation / Booking / Billing | `batch.dpi_*`, `verify-dpi` | Accrue, GL book, bill to due |
| getLoanAccountOverviewDetails | `dpic.overview_api` | dpi_* amount fields |
| getLoanAccountSummaryDetails | `dpic.summary_api` | `dpi_details` block |
| getLoanAccountBPIAmount | `dpic.restructuring_bpi_api` | `bpd_amount` |
| getPartPrepaymentBPIAmount | `dpic.part_prepayment_bpi_flow` | `bpd_amount` at rescheduling date |
| getLoanAccountPartPrepaymentDetails | `dpic.part_prepayment_details_flow` | live `bpd_amount` for PENDING row |
| fetchLoanForeclosureSimulationDetails | `dpic.foreclosure_sim` | `billed_dpi`, `bpd_amount` |
| getLoanForeclosureDetails | `dpic.foreclosure_details_api` | `billed_dpi_details`, `bpd_details` |
| loanRepayment | `dpic.repayment_e2e` | BILLED_DPI / PAID_BILLED_DPI appropriation |
| childLoanRepayment | `dpic.child_repayment_e2e` | JLG child DPI appropriation |
| loanAccountTransactionReversal | `dpic.repayment_reversal_e2e` | DPI restored on reversal |
| loanAccountAssetCriteriaJob | `dpic.npa_dpi_movement_e2e` | REGULAR_TO_NPA DPI_INT_INCOME legs |
| loanAccountRestructuring | `dpic.restructuring_smoke`, grace/multi-EMI | capitaliseAccruedDpi |
| individualChildLoanForeclosure / DCF | `foreclosure.dpi_waiver_smoke` | DPI waiver legs |
| Cross-EOD replay | `dpic.cross_eod_replay_134497` | Idempotent booking refs |

## Remaining gaps (no local harness)

| Surface | Risk | Notes |
|---------|------|-------|
| loanAccountPartPrepayment (write) | Medium | `loanAccountPartPrepayment` POST — ADV_BILLED_DPI |
| generateDPIPresentationFiles + reverse feeds | Medium | explicitly excluded |
| loanWriteoff | Medium | explicitly excluded |
| deathForeclosureInsuranceJob batch | Low | partial via waiver smoke |
| Product scheme DPI config APIs | Low | setup SQL only |

Run gap discovery: `kg flow <apiName>` + grep `BILLED_DPI` in orchestration.
