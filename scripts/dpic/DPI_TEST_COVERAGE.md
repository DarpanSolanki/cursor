# DPI test coverage map (workspace harness)

**Branch (accounting DPI):** `mfi_integration_v3.7.1` only (booking fix `77921d275f` must be in HEAD).  
**Canonical runner:** `DPI_REGRESSION_PROFILE=quick bash scripts/dpic/run_dpi_full_regression.sh` · `ntest run dpic.full_regression`  
**QA batch path:** `ntest api accounting <job> --batch --job-time <ms>` + `wait_batch_job.sh` → `COMPLETED`  
**Three-job proof:** `bash scripts/dpic/run_dpi_three_job_verify.sh` · `ntest run dpic.three_job_verify`  
**Booking-anchor / next-due seal:** `bash scripts/dpic/run_dpi_booking_anchor_e2e.sh` · `ntest run dpic.booking_anchor_next_due`

## Product rules (encode in harness — do not invent)

| Rule | Harness check |
|------|----------------|
| **Grace** | Stored `loan_due_details.overdue_date` gate only; first slice `start_date` = **due_date**; grace 0 (overdue=due) is valid — `verify_grace_dpi_e2e.sql` |
| **Splitting** | Month-end + EMI due seals (interest parity) — not single due→next-due collapse — `verify_dpi_accrual_slice_integrity.sql` |
| **Slice ownership** | Latest EMI due on/before segStart (not grace lastAnchor) — grace overlap E2E |
| **Booking** | Post on month-end OR any INT/PRIN EMI due day (not this-installment INT only) — `dpi-booking-posting-guard.sh` + `run_dpi_booking_anchor_e2e.sh` |
| **Billing** | Needs `accrual_posting_date`; next-EMI billing calendar may leave month-end unbilled until next due — documented exception below |
| **Fail gates** | `sealed_unposted` / `sealed_unbilled` via `verify_dpi_booking_billing_audit.sql` + `run_dpi_column_audit.sh` |

## Quick regression (`DPI_REGRESSION_PROFILE=quick`, target &lt;15–20 min)

```bash
bash scripts/dpic/reset_dpi_fixtures.sh   # also first step of full_regression
DPI_REGRESSION_PROFILE=quick bash scripts/dpic/run_dpi_full_regression.sh
# or: DPI_REGRESSION_PROFILE=quick ntest run dpic.full_regression
```

| Step | What |
|------|------|
| `fixture_reset` | Canonical LANs via `dpi_fixture_constants.sh` |
| `three_job_verify` | ntest calc→booking→billing + **column audit** (sealed→posted→billed) |
| `posting_guards` | Static Java guard: any-EMI-due booking anchor |
| `two_emi_full_chain` | **`DPI_CALENDAR_MODE=milestones`** (not daily May→Jul) + column audit |
| `grace_e2e` / `grace_overlap_e2e` | Grace gate + overlap ownership; overlap runs column audit |
| `booking_anchor_next_due` | Next-EMI due seal must post |
| `shg_parent_child_parity` | Parent = sum(children) |

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

# Full reset → single EOD chain → slice SQL (8060160)
ntest run dpic.three_job_verify_single_eod
```

**`wait_batch` in registry:** `batch.dpi_*` set `wait_batch: true` — `ntest run` polls `mfi_batch.batch_job_execution` until `COMPLETED` via `scripts/dpic/lib/wait_batch_job.sh`.

**`SEED_CALC_WINDOW`:** default **`0`** on `run_eod_dpi_only.sh` / `run_eod.sh` / `run_qa_demo.sh` / `run_full_happy_path.sh` / demo EOD. Value `1` runs `seed_calc_window.sql` (documented bypass INSERT — **not** for passing tests). Three-job harness **rejects** `SEED_CALC_WINDOW=1`.

## Column audit gate (post-batch, mandatory)

After real `ntest` batch jobs (`COMPLETED`), run:

```bash
bash scripts/dpic/lib/run_dpi_column_audit.sh <loan_account_id> <business_date>
# wired into: three_job_verify, two_emi (milestones/daily), grace_overlap (default), booking_anchor
```

| SQL | Checks |
|-----|--------|
| `verify_dpi_accrual_slice_integrity.sql` | start/end dates, contiguity, month-end/due seals, first slice on due_date, posted on any EMI due or month-end |
| `verify_dpi_booking_billing_audit.sql` | **`sealed_unposted`** (end≤biz **and** end is month-end or INT/PRIN due — open non-anchor windows excluded); **`sealed_unbilled`** (EMI seal day or next EMI due ≤biz); GL / due amount checks |

**Billing calendar exception (documented):** month-end seals may stay unbilled until the next INT/PRIN due day arrives (`sealed_unbilled` only fires when end is an EMI due day, or a later EMI due ≤ business_date).

Canonical LANs: `8060160` (standard 3-job), `8057160` (grace / two-EMI / booking-anchor), `116360` (SHG parity). **0 violations** required before ship.

## Fixture LANs (`lib/dpi_fixture_constants.sh`)

| Role | loan_account_id | LAN | Used by |
|------|-----------------|-----|---------|
| Standard regression | `8060160` | `6004044425` | posting calendar, EOD txn, billing UD, APIs, three_job |
| Grace / overlap / two-EMI | `8057160` | `6004041325` | grace E2E, overlap, two_emi, booking_anchor |
| SHG parent parity | `116360` | `6000001074` | SDCP-11012 parent=sum(children) |
| Child JLG repayment | `8048470` | `6004029335` | childLoanRepayment DPI |

**Why 8057160/116360 were empty:** `purge_local_dpi_all.sql` + setup SQL clears `dpi_accrual_details` but accruals are only recreated by **`dpiAccrualCalculation`** — scripts that asserted without calling the batch job saw zero rows.

## Canonical local job invocation (QA-shaped)

```bash
bash scripts/bin/novopay-service.sh ensure accounting --compile
bash scripts/bin/agent-ops.sh before-test dpiAccrualCalculation

ntest run batch.dpi_calc
ntest run batch.dpi_booking
ntest run batch.dpi_billing

LOAN_ACCOUNT_ID=8060160 bash scripts/dpic/run_eod_dpi_only.sh

source scripts/dpic/lib/dpi_demo_fixture.sh
dpi_call_batch dpiAccrualCalculation "$JOB_TIME"
dpi_call_eod_chain "$JOB_TIME"   # calc → booking → billing
```

Poll completion: `scripts/dpic/lib/wait_batch_job.sh <jobName> <job_time_ms> <run_started_epoch>`  
Batch status: `mfi_batch.batch_job_execution` where `status=COMPLETED`.

## Audit: insert-only vs job-first

| Path | Classification | Notes |
|------|----------------|-------|
| `run_grace_*`, `run_dpi_two_emi_*`, `run_dpi_shg_*`, `run_dpi_booking_anchor_*` | ✅ Real jobs | setup SQL then batch + wait |
| `run_dpi_posting_calendar_regression.sh` | ✅ Real jobs | daily calc+booking loop + billing |
| `run_dpi_eod_txn_regression.sh` | ✅ Real jobs | calc → month-end booking → billing |
| `run_eod_dpi_only.sh` | ✅ Real jobs | `SEED_CALC_WINDOW=0` default; ntest batch chain |
| `run_dpi_three_job_verify.sh` | ✅ Real jobs | reset → setup SQL → ntest calc/booking/billing |
| `run_dpi_post_eod_verify.sh` | ⚠️ Assert only | requires prior job run |
| `seed_calc_window.sql` | ❌ Bypass | zero-amount anchor INSERT — opt-in `SEED_CALC_WINDOW=1` |
| `seed_dpi_accrual_history_bloat.sql` | ❌ Bypass | perf fixture only (`run_dpi_batch_perf_e2e.sh`) |
| `run_eod.sh` | ⚠️ Hybrid | curl batch APIs; `SEED_CALC_WINDOW=0` default |

**Demo loan:** `8060160` / `6004044425` · **job_time:** `1782563400000`

## QA job run guide (calc → booking → billing)

**Order (always):** `dpiAccrualCalculation` → `dpiAccrualBooking` → `dpiBilling`.  
EOD runs all three in that sequence for the same `job_time` (business date).

| Job | Writes |
|-----|--------|
| `dpiAccrualCalculation` | Inserts/updates `dpi_accrual_details` slices — seals on month-end or next EMI INT/PRIN due |
| `dpiAccrualBooking` | Sets `accrual_posting_date` + ref + GL for sealed unposted rows (any EMI due or month-end) |
| `dpiBilling` | Sets `billing_posting_date` + creates/updates `loan_due_details` DPI due |

**Sample verify (booking-anchor LAN):**

```bash
bash scripts/dpic/run_dpi_booking_anchor_e2e.sh
# or after jobs:
bash scripts/dpic/lib/run_dpi_column_audit.sh 8057160 2026-06-15
```

```sql
SELECT id, start_date::date, end_date::date, total_accrued_amount,
       accrual_posting_date::date AS apd, billing_posting_date::date AS bpd
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = 8057160 AND is_deleted = false AND total_accrued_amount > 0
ORDER BY end_date, id;
```

| After | Expect |
|-------|--------|
| calc | rows exist; next-due seal may have `apd` NULL until booking |
| booking | every `end_date <= biz` with amt>0 has `apd` (incl. prior-EMI → next due) |
| billing | EMI-seal / billable rows have `bpd`; month-end may wait for next due; column audit 0 violations |

**Out of scope (per QA plan):** `generateDPIPresentationFiles` quartet, `loanWriteoff`.

## Covered (registry / scripts)

| Surface | Registry / script | DPI role |
|---------|-------------------|----------|
| dpiAccrualCalculation / Booking / Billing | `batch.dpi_*`, `dpic.full_regression` | Accrue, GL book, bill to due |
| Booking next-due seal | `dpic.booking_anchor_next_due` | 77921d275f class |
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

## Deprecated wrappers

| Wrapper | Prefer |
|---------|--------|
| `run_dpi_regression.sh` | `DPI_REGRESSION_PROFILE=standard run_dpi_full_regression.sh` |
| `run_dpi_max_regression.sh` | `DPI_REGRESSION_PROFILE=full …` |
| `scripts/bin/dpi-sanity.sh` | `DPI_REGRESSION_PROFILE=quick …` |

Run gap discovery: `kg flow <apiName>` + grep `BILLED_DPI` in orchestration.
