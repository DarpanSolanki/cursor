# DPIC v1 — System Knowledge of the Flow (the spine)

> Branch `feature/delayed_payment_interest` (accounting-v2 + initial-setup), tip `c054f7149` (2026-06-09). This is the navigable **flow index** — each step cites code `file:line` and links to the deep section in [`01-implementation-spec.md`](01-implementation-spec.md). Query the live chain with `claude/kg/bin/kg flow dpiAccrualCalculation|dpiAccrualBooking|dpiBilling`.

DPI = **Delayed Payment Interest** — a 5th loan component (P / I / Penalty / Fee / **DPI**) levied on `(overdue_principal + overdue_interest)` for EMIs past their grace window. It **mirrors INTEREST** mechanically: accrue daily → book → bill on the next EMI date → appropriate on repayment → suspend/recover across NPA. No compounding (never accrues on outstanding DPI).

## End-to-end flow

```
                       (product scheme: rate, grace, days-in-year, DPI go-live)
 daily ──► [1] dpiAccrualCalculation ──► dpi_accrual_details (status=ACCRUED, no GL)
 daily ──► [2] dpiAccrualBooking      ──► GL accrual posting + accrualTransactionRefNumber
 EMI  ──► [3] dpiBilling              ──► loan_due_details DPI row (component_type=DPI), BILLED
 pay  ──► [4] RepaymentApproppriation ──► DPI at position 3 (after I, before Penalty/Fee)
 NPA  ──► [5] DpiNpaMovementService   ──► DPI to/from suspense alongside interest
 close──► [6] lifecycle hooks         ──► force-bill unbilled DPI on foreclosure, etc.
 view ──► [7] GetDpiAccrualDetails    ──► Loan 360 surfacing
```

## Step detail (code-anchored)

**[1] Accrual calculation** — `Request dpiAccrualCalculation` → `dpiAccrualCalculationBatchProcessor` ([loans_orc.xml:2450](../../novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml#L2450)). Spring-Batch: `ItemReader`→`DpiAccrualCalculationItemProcessor:29`→`ItemWriter`→`DpiAccrualCalculationBatchService`. Computes DPI for the window via the calc service and persists a `dpi_accrual_details` row (`DpiAccrualDetailsEntity:28`, table `dpi_accrual_details`) with `status=ACCRUED` — **no GL yet**. Spec §8.

**[2] Accrual booking** — `Request dpiAccrualBooking` → `dpiAccrualBookingBatchProcessor` ([loans_orc.xml:2465](../../novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml#L2465)). Reads `ACCRUED` rows, posts the GL accrual leg via `postTransaction`, stamps `accrualPostingDate` + `accrualTransactionRefNumber` (`DpiAccrualDetailsEntity:54-55`). `is_reversible=false`. Spec §9.

**[3] Billing** — `Request dpiBilling` → `dpiBillingBatchProcessor` ([loans_orc.xml:2480](../../novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml#L2480)). On the **next EMI due date** (not the missed-EMI date), moves accrued DPI into `loan_due_details` as a row with `component_type = DPI` (`AssetsConstants.DPI`), making it billed/dueable. **Post-maturity** (no next installment) the due date is the next monthly anchor — `maturity_date` rolled forward past the accrual `end_date` — and billing defers until that anchor (`DpiBillingBatchService` + `DpiBillingItemReader` carry `da.end_date, la.maturity_date`). DPD numerator picks it up with no extra code (`LoanAccountDpdCalcBatchProcessor` already sums `loan_due_details`). Spec §10.

**[4] Repayment appropriation** — `RepaymentApproppriationProcessor`. DPI sits at its **product-configured sequence slot**; legacy product rows (created before DPI joined the schema) fall back to `FALLBACK_DPI_POSITION = 3` ([RepaymentApproppriationProcessor.java:48](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java#L48), seating logic :98-102). Paid DPI is published to the EC as `dpi_amount` (:129) and flows into `loan_account_payments_details.dpi_amount`. EMI knock-off rule unchanged (DPI residual does not block knock-off). Spec §6.

**[5] NPA movement** — `DpiNpaMovementService.postForwardMovement():45` / `postReverseMovement():50` move DPI to/from suspense in lock-step with interest; NPA repayment recognises paid DPI out of suspense (`INT_SUS_AMT` + DPI suspense legs, see RepaymentApproppriationProcessor.java:143). Spec §6/§7.

**[6] Lifecycle hooks** — on foreclosure, `MarkUnbilledDpiAsBilledOnForeclosureProcessor:18` (`process():24`) force-bills any still-accrued-but-unbilled DPI before closure. On **restructuring**, `CapitaliseAccruedDpiOnRestructureProcessor` (wired after `generateLoanAccountRestructuringRepaymentScheduleProcessor` in `loanAccountRestructuring`) capitalises accrued-unbilled DPI onto the first new installment as a `component_type=DPI` due and closes the source accrual via `markBilledTillDate`; billed DPI dues need no handler (preserved by the component-agnostic due-delete). Part-prepayment / death-foreclosure DPI surfacing tracked in [05-open-questions.md](05-open-questions.md).

**[7] Calculation engine** (load-bearing) — `DPICalculationService.calculate(loanAccountId, start, end[, DpiSchemeConfig])` ([:48/:57](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/dpi/calculation/DPICalculationService.java#L48)). Formula (`:21`, `:81`): **`DPI = overdueBase × (annualRate/100) × days / daysInYear`**, rounded to whole units, via the shared `InterestCalculationUtil.computeInterest(...)`. `overdueBase` = sum of `[PRINCIPAL, INTEREST]` overdue rows only (`LoanDueDetailsDAOService.getDueDetailsByOverDueDate`). Per-loan rate/grace/days come from `DpiSchemeConfigResolver` → `DefaultDpiSchemeConfigResolver` (v1 reads scheme-level fields; swap to per-frequency table when Q4 lands, calc side unchanged). Spec §7.

## GL posting & amounts

DPI legs mirror INTEREST in the rule engine; placeholders `DPI_*` (e.g. accrual, billed, waived, suspense). Resolution algorithm and the DPI `reference_code`/`source_amount` mapping are in [`08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md) + the DPI rule audit [`02-code-vs-sheet-audit.md`](02-code-vs-sheet-audit.md). Posting mechanics worked end-to-end (with amount maths) in the DFC reference [`../accounting/worked-examples/death-foreclosure-walkthrough.md`](../accounting/worked-examples/death-foreclosure-walkthrough.md). Use the `posting-rule-resolver` skill before running SQL against `transaction_master`.

## Data model touched

`dpi_accrual_details` (new) · `loan_due_details` (+DPI rows) · `loan_account_payments_details.dpi_amount` · `transaction_reversal_details.dpi_amount` · code-master seeds (`V9000758__add_dpi_code_master_seed.sql` in initial-setup: `APP_LOGIC_DPI@pos3`, `DPI_APBL`, `DPI_GO_LIVE_DATE`). Schema detail: spec §4.

## Status (2026-06-09) — what's DONE vs PENDING

**Done on branch:** all 3 batch jobs (accrual calc → booking → billing) + GL wiring; `DPICalculationService` + scheme-config resolver; repayment appropriation (DPI @ pos 3, setup-driven); NPA forward/reverse movement; foreclosure force-bill hook; Loan-360 accrual surfacing (`GetDpiAccrualDetailsProcessor`); reversal flow carries `dpi_amount`; DPD base includes DPI.

**Pending (Q-list, see [05-open-questions.md](05-open-questions.md)):** per-frequency DPI config table (Q4) for Loan-360 "Original/configured" sub-fields; full lifecycle DPI surfacing in Part-Prepayment / Auto-Closure / Restructuring / Death-Foreclosure previews; push-to-collection payload + Total-Outstanding recompute; runtime verification once QA seeds land (NOT runtime-verified).

> Reconcile against code before any change — this is the index; the cited `file:line` and `01-implementation-spec.md` are the source of truth.
