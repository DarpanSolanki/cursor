# DPIC v1 — Delayed Payment Interest (LMS Accounting)

> Branch: `feature/delayed_payment_interest` (accounting-v2 + initial-setup), tip `c054f7149` 2026-06-09 — the latest DPIC dev lineage (more complete than `feature/dpic-v1`). `upstream/sli_dpic` is a separate bank-side integration branch.
> **Flow spine: [04-dpic-flow.md](04-dpic-flow.md)** (system knowledge, code-anchored) — `claude/kg/bin/kg flow dpiAccrualCalculation`.
> Status: **development done on branch** — the full accrual→booking→billing pipeline is implemented (all 3 batch jobs + GL wiring), DPI calc service, scheme-config resolver, repayment appropriation (DPI @ pos 3), NPA forward/reverse movement, foreclosure force-bill hook, Loan-360 accrual surfacing, reversal `dpi_amount`, DPD base includes DPI. NOT runtime-verified (QA seeds pending). Remaining: per-frequency config table (Q4), full lifecycle surfacing (Part-Prepayment / Auto-Closure / Restructuring / Death-Foreclosure previews), push-to-collection (see [05-open-questions.md](05-open-questions.md)).
> UD: [`/home/darpan/darpan/UDs/UD_LMS_Delayed Payment Interest v1.3.docx`].

---

## What is DPIC

DPI = **Delayed Payment Interest** — a 5th loan component (alongside Principal / Interest / Penalty / Fee) levied on `(overdue_principal + overdue_interest)` for EMIs past their grace window. Calculated per-frequency at the Product Scheme level (rate + grace + days-in-year). Per UD §5.2 it sits **3rd in the appropriation order** — after Interest, before Penalty / Fee.

**Key behavioural rules (locked from UD + sample-calc):**

- DPI accrues on `(overdue_P + overdue_I)` only — **never on outstanding DPI itself** (no compounding).
- DPI accrued for a missed EMI is **billed on the next EMI due date**, not the missed-EMI date.
- EMI knock-off rule (UD §5.5) is unchanged: settled when `paid(P+I) >= due(P+I)`. DPI / PINT / FEE residuals do not block knock-off — and the existing `UpdateLoanInstallmentDetailsProcessor:51-55` already implements this correctly.
- DPD numerator (UD §5.5) is unchanged: `LoanAccountDpdCalcBatchProcessor` already sums all components in `loan_due_details`. DPI rows surface naturally without code change.
- Reversal: standard `reverseTransaction` flow handles DPI via `(transaction_type, transaction_sub_type)` mapping. Only `LOAN_REPAYMENT/CASH` and `LOAN_REPAYMENT/EXCESS_AMT` are reversible (`is_reversible=true`); DPI accrual + billing must stay `is_reversible=false`.

## What's done in this branch

| Concern | Change |
|---|---|
| `loan_due_details.component_type` for DPI rows | Added constant `AssetsConstants.DPI = "DPI"` |
| Asset-criteria appropriation map | Added `APPROPPRIATION_DPI_COMPONENT = "APP_LOGIC_DPI"` + map entry |
| Repayment appropriation processor | DPI accumulator + setup-driven sequence reading (forward-compatible with sequence_5; DPI position from product setup, fallback to masterdata-default 3 only for pre-Q3 rows) + DPI routes to installment-side bucket in `LIQ_INSTL_CHRG_COMP` mode |
| DPI calc service | `DPICalculationService.calculate(loanAccountId, accrualStart, accrualEnd)` returning rounded DPI for the window. Reads overdue base via `LoanDueDetailsDAOService.getDueDetailsByOverDueDate(...)` for `[PRINCIPAL, INTEREST]` only. Uses existing `InterestCalculationUtil.computeInterest(...)` for the `base × rate × days / daysInYear` formula. |
| DPI scheme-config resolver (per-loan-account config) | Interface `DpiSchemeConfigResolver` + `DefaultDpiSchemeConfigResolver` (v1 stub reading scheme-level fields). Swap to per-frequency table once Q4 lands without changing the calc-side. |
| Code-master seeds (product-level Flyway) | `V9000758__add_dpi_code_master_seed.sql` — APPROPRIATION_LOGIC/LOANS gets APP_LOGIC_DPI@pos3 (PNLT shifts to 4, FEES to 5); DPI_APBL/DEFAULT/{YES,NO}; DPI_GO_LIVE_DATE/{JLGDL,INDL_LOAN,SHGDL} master rows. |
| Constants in `AccountingConstants` | `DPI_APBL_DATATYPE`, `DPI_APBL_VALUE_YES/NO`, `DPI_GO_LIVE_DATE_DATATYPE`, `DPI_AMOUNT`, `PRODUCT_SCHEME_DPI_APPLICABLE` |

## What's deferred (still pending; the batch jobs below are now DONE — see [04-dpic-flow.md](04-dpic-flow.md))

- ~~DPI Accrual + Billing batch jobs~~ — **DONE** on `feature/delayed_payment_interest`: `dpiAccrualCalculation` → `dpiAccrualBooking` → `dpiBilling` (Reader/ItemProcessor/Writer/BatchService each), wired in `loans_orc.xml:2450/2465/2480`.
- **Loan 360 7 sub-fields** — base accrual surfacing is live (`GetDpiAccrualDetailsProcessor`); the "Original/configured" sub-fields still depend on the per-frequency config table (Q4).
- **Lifecycle handlers** (Part Prepayment, Auto Closure, Death Foreclosure) — foreclosure force-bill hook is in (`MarkUnbilledDpiAsBilledOnForeclosureProcessor`); remaining lifecycle preview/posting DPI surfacing pending.
- **Restructuring — DONE** (product clarified 2026-06-12): billed DPI dues are already preserved like billed interest dues (component-agnostic due-delete); accrued-unbilled DPI is capitalised onto the first new installment via `CapitaliseAccruedDpiOnRestructureProcessor` (`loanAccountRestructuring`, after schedule-gen) — reuses `getUnbilledAccruedAmountTillDate` + `markBilledTillDate`. No waiver, no upfront.
- **Post-maturity DPI billing — DONE** (product clarified 2026-06-12): accrual already continues post-maturity (loan stays `ACTIVE`, `past_due_days>0`, no maturity ceiling); billing now lands on the next monthly anchor (`maturity_date` rolled forward past the accrual `end_date`) instead of the overdue-installment fallback. v1 monthly only.
- ~~Push-to-collection~~ — **accounting backend DONE** (verified 2026-06-12): `LoanRecurringPaymentBatchProcessor` emits `dpi_due` (:178) + `dpi_overdue` (:182) and includes DPI in `getTotalOverDueAmount` (:423), `getTotalDueAmount` (:444), the component-agnostic `total_outstanding_amount` (:149) and the collection `amount` (:212). Only the Collections-app UI DPI column (other team) remains. (The earlier "pending" call traced the wrong processor `PopulateLoanAccountCollectionRequestProcessor` — closure-only, no amounts.)

## Open dependencies (mailed)

See [05-open-questions.md](05-open-questions.md) for the live Q-list and ownership.

## Files added / changed

```
novopay-platform-accounting-v2/
├── src/main/java/in/novopay/accounting/common/AssetsConstants.java          (modified)
├── src/main/java/in/novopay/accounting/common/AccountingConstants.java      (modified)
├── src/main/java/in/novopay/accounting/loan/repayment/processor/
│   └── RepaymentApproppriationProcessor.java                                (modified)
└── src/main/java/in/novopay/accounting/loan/dpi/calculation/                (new)
    ├── DpiSchemeConfig.java
    ├── DpiSchemeConfigResolver.java
    ├── DefaultDpiSchemeConfigResolver.java
    └── DPICalculationService.java

novopay-platform-initial-setup/
└── flyway/sli/masterdata/sql/product/
    └── V9000758__add_dpi_code_master_seed.sql                               (new)
```
