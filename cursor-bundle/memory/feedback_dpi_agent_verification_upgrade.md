# DPI agent verification upgrade (mandatory after SDCP-10497/10529 embarrassment)

**Standing rule for any agent touching DPI or declaring "fixed / PASS / QA ready".**

## Never say

- "Everything is fixed" / "QA happy path will pass" / "suite is hardened"
- "PASS" without naming **commit SHA** + **registry case IDs**
- "Mirrors interest" without grep-reading **both** calc precompute + booking gate same session

## Always say (tiered honesty)

| Claim | Requires |
|-------|----------|
| Static: invariant holds | Full diff of calc/booking/billing since last sign-off + invariant checklist below |
| Runtime: scenario X PASS | Named `ntest run dpic.*` on **that SHA** + SQL parity output |
| QA-ready | Above + explicit "NOT verified on QA1 LAN ___" until user confirms deploy |

## DPI flow spine @ `a8f822cf0+` (authoritative order)

**BOD chain** (`LoanSystemDailyJobLoader`): DPD → asset → penal → **interest calc/book/bill** → **dpiAccrualCalculation → dpiAccrualBooking → dpiBilling**

**job_time** = business date after EOD advance (often D+1 00:00 IST for month-end close).

### 1. Calc (`DpiAccrualCalculationBatchService`)

- **Reader**: `past_due_days > 0`, `dpi_applicable`, LMS-BOD failure audit clear.
- **Window**: from max `end_date` (or first overdue due) through `today` (trunc job date).
- **precomputeDaySnapshots** (daily): base += PRIN/INT with `due <= segStart`; anchor INT with **`due <= segStart`** (NOT segStart+1 — `a8f822cf0`).
- **Boundary walk**: `segEnd = nextBoundary(segStart)` = min(next EMI due, next month-end, today) — **inclusive end_date on boundary**.
- **Slice split**: new row when `open==null || isLastDayOfMonth(segStart)`; else extend open row.
- **Amount**: `DPICalculationService.calculateSegment` — grace gate, interest start, preloaded `segOverdueBase`, HALF_UP to int + carry.
- **Rows without boundary end_date** (in-flight `end_date=today`): **must not book** until boundary.

### 2. Booking (`DpiAccrualBookingBatchService`)

- Eligible: unposted, amount>0, **`end_date <= businessDate`**.
- Post gate: **`isLastDayOfMonth(end_date) OR end_date in EMI due days`** (inclusive — NOT businessDate, NOT dayBefore).
- GL: `value_date = end_date`; `accrual_posting_date = businessDate`.

### 3. Billing (`DpiBillingBatchService`)

- Reader: anchor installment with overdue accrual context.
- Bills when **next EMI date <= businessDate**; aggregates **`isAccruedUnbilled`** rows per anchor installment.
- `loan_due_details` DPI row; `value_date = next EMI due date`.
- **Chain**: no billing without `accrual_posting_date` on rows.

### Amount parity invariant

`SUM(posted total_accrued_amount) = SUM(GL original_amount) = SUM(DPI due_amount)` per billing cycle — `verify_dpi_amount_parity.sql`.

## Invariant checklist (grep every DPI change)

1. precompute: **same cutoff** for base and anchor (`<= segStart`)
2. calc `end_date` lands **only** on month-end or EMI due (except in-flight cap at `today`)
3. booking gate uses **slice end_date**, not job_time
4. billing waits for **next EMI** and **posted** accruals
5. go-live filters dues (`postGoLiveDueDays`) and maturity skip
6. compare `InterestAccrualBookingBatchService.isAccrualPostingDate` + interest calc segmentation

## Scenario matrix (minimum registry coverage)

| EMI due ordinal | Registry case |
|-----------------|---------------|
| 2nd of month | `dpic.posting_calendar_regression` |
| 1st of month | `dpic.emi_first_anchor_regression` |
| 15th go-live | `dpic.go_live_ud` |
| NPA + month-end job_time | `dpic.eod_txn_regression` |
| Amount parity | `verify_dpi_amount_parity.sql` in posting calendar |

**Harness must**: daily calc+booking per calendar day; END_DATE through **next EMI** before billing assert.

## Bug history (do not repeat)

| Bug | Wrong | Right @ current |
|-----|-------|-----------------|
| SDCP-10497 booking | gate on `businessDate` | gate on inclusive `end_date` |
| exclusive end_date | `dayBefore` posting | inclusive boundary walk `085284b1f` |
| SDCP-10529 partial bill | unposted slices | booking before billing |
| 1st EMI month-end | anchor `<= segEnd` | anchor `<= segStart` `a8f822cf0` |
| False PASS | replay on due days only | QA daily EOD |

## Residual risks to watch (not proven closed)

- Calc L114-115: null snapshot advances `+1 day` while main loop jumps `segEnd` — verify no double-path drift.
- `loadDueDayKeys` uses **all** due components (includes DPI rows?) for booking EMI set — confirm intentional.
- `client_reference_number` time-based — replay dedupe risk (platform gap).
- Rounding carry across slices — small ₹ drift if parity SQL not run.
- QA1 loan shapes (604565, 7038560, 6801460) ≠ local fixture 8060160 until replayed there.

## Agent workflow on every user push

1. `git pull` + `git diff HEAD~1` on `batchnew/dpi/**` + `DPICalculationService`
2. Run invariant checklist (write pass/fail per line)
3. Run full registry matrix on SHA
4. Only then discuss release — never before step 3
