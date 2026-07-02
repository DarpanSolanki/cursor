# DPI test coverage map (workspace harness)

**Canonical runner:** `ntest run dpic.extended_regression`  
**Demo loan:** `8060160` / `6004044425` · **Child JLG:** `8048470` / `6004029335` · **job_time:** `1782563400000`

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
