# DPIC v1 — Open Questions (Live)

> Mirror of the dependency mail sent to Vasanthi (Product) + Rohit (Loan Product / Product Scheme).
> Update status here as answers come back.

| ID | Owner | Question | Status |
|----|-------|----------|--------|
| Q1 | Vasanthi | 6 new `(transaction_type, transaction_sub_type)` literals + `is_reversible=false` for accrual+billing | Open — **mitigated**: code paths now resolve sub-type via `System.getProperty(...)` overrides (`novopay.accounting.dpi.txn.subtype.normal.accrual` / `.npa.accrual` / `.normal.billing`) so production can swap without redeploy if literals differ |
| Q2 | Vasanthi (Product Ops) | GL setup (6 GLs + 28 accounting rules) via webapp Create General Ledger / Accounting Rule screens | Open |
| Q3 | Rohit | `loan_product_asset_criteria` schema: add `sequence_5` + backfill `APP_LOGIC_DPI` after `APP_LOGIC_INT` per row | Open |
| Q4 | Rohit | New per-frequency child table `product_scheme_repayment_frequency_details` covering DPI Applicable + Grace + Calc Days/Year + Spread + Interest Setup; migrate scheme-level singletons | Open |
| Q5 | Rohit | Confirm boundary: DPI calc service + accrual/billing/appropriation = our side; per-frequency config + masterdata + UI = Rohit's side | Open |
| Q6 | Rohit | Confirm DPI track writes `loan_due_details.component_type = "DPI"` | Open |

## Working assumptions (proceed unless flagged wrong)

1. `loan_due_details.component_type = "DPI"` (3-letter, matches APP_LOGIC_DPI + Loan 360 column header).
2. `DPI_APBL` code values = `YES` / `NO`.
3. DPI position is **setup-driven** per product via `loan_product_asset_criteria.sequence_*` (Q3). Until Q3 lands and existing rows are migrated, the processor falls back to position 3 from the masterdata seed (V000117, UD §5.2 image 2).
4. DPI accrual + billing follow `interestAccrualCalculation` + `interestAccrualBooking` + `loanAccountBilling` batch shape.
5. DPI rate / grace / days-in-year read **per-frequency** from Q4 table (v1 monthly only).
6. **Interest-on-Interest NOT applied** — DPI accrues on `(overdue_P + overdue_I)` only.
7. DPI billed for missed EMI on the **next EMI due date**, not the missed-EMI date.
8. Day-zero / pre-go-live overdue handling parked for v1.
9. Reversal: standard `reverseTransaction` flow, no DPI-specific path.
10. v1 = monthly repayment frequency only.

## Product clarifications resolved (2026-06-12)

- **Restructuring** — DPI treated exactly like normal interest; no waiver, no upfront. Billed DPI → like billed interest dues (already preserved by the component-agnostic due-delete). Accrued-unbilled DPI → capitalised onto the first new installment like BPI. Implemented: `CapitaliseAccruedDpiOnRestructureProcessor` (R4 done).
- **Post-maturity DPI** — DPI keeps accruing daily on overdue P+I after maturity (loan stays `ACTIVE`; already handled) and stops when overdue clears. Billing lands on the next monthly anchor (`maturity_date` rolled forward past the accrual `end_date`), per the "DPI & DPD Logic" worksheet. Implemented in `DpiBillingItemReader` + `DpiBillingBatchService`. v1 monthly only.

## Accrual-window + precision — verified vs UD + sample (2026-06-12)

- **Window model CONFIRMED (UD + sample).** UD: *"calculate DPI on the **total overdue amount** (overdue principal + overdue interest)"* and *"handle DPI accruals using the **same logic currently applied for interest income accruals**."* Sample `DPI & DPD 360 Logic Monthly` reconstructs exactly: accrual window = **earliest overdue installment → accrual date**, on the **combined** declining overdue balance, **resuming from last accrual end**; billed on the next monthly anchor. So DPI = interest-accrual *mechanics* on the *overdue base from the overdue date* — **combined, NOT per-installment** (the earlier penal-style caveat is **withdrawn**). Window-start fix `8f1be5234`: `DpiAccrualCalculationBatchService` now uses `getEarliestInstallmentDateWithUnpaidDpdComponents` (the canonical earliest-unpaid-installment query; DPD uses it too) instead of `getLatestLoanInstallmentDetailsEntity` (next *future* EMI, which skipped every overdue loan on first accrual).
- **OPEN — accrual rounding/precision vs sample (NOT runtime-verified).** `DPICalculationService.calculate()` (loan/dpi/calculation/DPICalculationService.java:69-82) reads `overdueBase` **once as-of window-start**, applies a **single flat rate × days**, and `setScale(0, HALF_UP)` **per call**. Under daily cadence the declining balance + the 24→22% rate change are captured day-by-day — BUT each daily accrual is rounded to whole ₹, whereas the sample rounds **once at month-end** (₹125 for May). Per-day rounding can run a few ₹ high (segment-1: 7×15=105 vs sample 100). Any **multi-day catch-up** window (job gap / day-zero) uses a flat start-of-window base (no intra-window segmentation) — bounded by the parked **Day-Zero** item (assumption 8; UD "Day Zero Impact"). **QA action:** seed the sample loan (EMI 10000=2000I+8000P, overdue 05-05, partials 05-20/05-30, ROI 24→22% on 05-21) and assert month-end accrual **125**, next-anchor accrual **6**, billed **131**. Confirm rounding cadence (per-day vs per-period) with Product.

## Branch-state corrections — verified 2026-06-12 vs live `feature/delayed_payment_interest` (forward-ported to 3.5.0)

01-implementation-spec.md describes the older `feature/dpic-v1`@3.3.2 and is stale on these points (verified file:line in code/Flyway this turn):
- Flyway names: `dpi_accrual_details`=**V000187** (not V000186); code-master seed=**V000119__add_code_masters_for_dpic.sql** (not V9000758); +V000188 (dpi_amount cols), V000190 (product_scheme_frequency_details), V000193 (prepayment DPI-waiver cols), V000194 (asset_criteria sequence_5); **V000450__added_api_master_for_dpi_batch_jobs.sql** (platform_master — registers `dpiAccrualCalculation`/`dpiAccrualBooking`/`dpiBilling` in `api_master`, service ACCOUNTING; added 2026-06-12, mirrors V000039).
- `APP_LOGIC_DPI` is seeded at **position 5** (no PNLT→4/FEES→5 reorder). Position 3 survives only as `RepaymentApproppriationProcessor.FALLBACK_DPI_POSITION` for legacy rows.
- **`DPI_GO_LIVE_DATE` is NOT seeded** by any Flyway — manual/webapp only if needed.
- **Q3 (asset_criteria sequence_5) and Q4 (per-frequency table) are RESOLVED & SEEDED** (V000194, V000190) — no longer open.
- Accrual-booking `System.getProperty` overrides removed; only `.normal.billing` / `.npa.booking` / `.int.income` remain; accrual sub-types `DPI_NORMAL_ACCRUAL`/`DPI_NPA_ACCRUAL` are hardcoded.
- Lifecycle handlers for foreclosure / part-prepayment / death-foreclosure / NPA movement are implemented in code (doc says "not started").
- Release/QA reference (business, no code): `claude/dpic/DPIC_v1_Release_and_QA_Guide.pdf`.
