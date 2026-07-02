# DPI UD test matrix — gap class → harness (mandatory gate)

**Purpose:** Every DPI/DPIC gap class must map to a **registry case** or explicit **open gap**. Ship-loop injects `dpic.ud_compliance` on **any** DPI path touch (batch, `loan/dpi/*`, `scripts/dpic/*`).

**Mandatory before DPI ship:** `ntest run dpic.ud_compliance` (also `agent-ops.sh verify-dpi` → same).

## Batch / UD §5.4 (calc → book → bill)

| Gap class | Symptom | Harness | SQL / assert |
|-----------|---------|---------|--------------|
| Go-live base | Pre-go-live EMIs in `base_amount` | `dpic.go_live_ud` / `ud_compliance` | `verify_go_live_ud_e2e.sql` — base = post-go-live eligible only |
| Maturity &lt; go-live | Accrual on closed/matured loan | `dpic.go_live_ud` | Temp maturity patch; expect 0 accrual rows |
| Posting calendar | Unposted rows on EMI due / month-end | `dpic.go_live_ud` | `verify_dpi_posting_calendar.sql` — interest-accrual posting pattern |
| No go-live date | Accrual without masterdata date | `dpic.certify_scenarios` (pre-EMI LAN) + code gate | Skip when `DPI_GO_LIVE_DATE` missing |
| Grace period | Base before grace+1 | `dpic.grace_e2e` / `ud_compliance` | `setup_grace_dpi_e2e.sql` |
| Multi-EMI anchor | Wrong slice / installment anchor | `dpic.multi_emi_installment_e2e` / `ud_compliance` | `setup_multi_emi_dpi_e2e.sql` |
| Cross-EOD booking idempotency | 134497 duplicate client ref | `dpic.cross_eod_replay_134497` | Numeric bill ref parity |
| Billing → due | DPI not on `loan_due_details` | `batch.dpi_billing` + `verify_dpi_post_eod.sql` | Extended regression |
| NPA income movement | REGULAR↔NPA DPI legs | `dpic.npa_dpi_movement_e2e` | `dpi_gl_verify.sh` |
| Product filter | Non-DPI product in calc reader | Reader `dpi_applicable=YES` | Certify fresh LAN on 6367 |

## API read surfaces

| Gap class | Harness |
|-----------|---------|
| Overview `dpi_*` amounts | `dpic.overview_api` |
| Summary `dpi_details` | `dpic.summary_api` |
| Foreclosure sim `billed_dpi` / `bpd` | `dpic.foreclosure_sim` |
| Foreclosure details block | `dpic.foreclosure_details_flow` |
| Part-prep BPI / details | `dpic.part_prepayment_bpi_flow`, `part_prepayment_details_flow` |
| Restructuring BPI | `dpic.restructuring_bpi_api` |

## Write / GL paths

| Gap class | Harness |
|-----------|---------|
| Repayment appropriation | `dpic.repayment_e2e` |
| Child repayment | `dpic.child_repayment_e2e` |
| Repayment reversal | `dpic.repayment_reversal_e2e` |
| Part-prep TRIAL components | `dpic.part_prepayment_write_e2e` |
| ICF / DCF foreclosure posting | `dpic.foreclosure_write_e2e`, `foreclosure.dpi_waiver_smoke` |
| Restructuring capitalise | `dpic.restructuring_smoke` |

## Workspace / process gaps (not code bugs)

| Gap class | Mitigation |
|-----------|------------|
| Wrong git branch (`mfi_integration_*` vs feature) | `dpi-feature-branch-gate.mdc`, `ensure-dpi-branches.sh` |
| Agent sign-off without EOD | `dpi-sanity.sh` → `ud_compliance` only |
| Happy-path single overdue only | `certify_dpi_scenarios` (3 fresh LANs) |
| KG stale on branch switch | `kg-switch.sh` on checkout |

## Still open (no local harness — track in `DPI_TEST_COVERAGE.md`)

| Gap class | Risk |
|-----------|------|
| Part-prep REAL / maker-checker | Medium |
| `generateDPIPresentationFiles` | Medium (excluded) |
| `loanWriteoff` DPI appropriation | Medium (excluded) |
| Death foreclosure insurance batch | Low |

## QA1 replay (2026-06) — fixed in code, data needs ops

Loans **5934060**, **750461**: bad historical rows — deploy fix then replay EOD or ops SQL cleanup; harness prevents recurrence.
