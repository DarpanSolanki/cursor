# DPI go-live / maturity / posting gaps (QA1 2026-06)

**Symptoms:** Loan **5934060** — `dpi_accrual_details.base_amount` included Jan–Apr pre-go-live overdues (go-live **15-04-2026** JLGDL). Loan **750461** — `maturity_date` before go-live still accrued. Apr 30–May 7 accrual slices unposted (booking date vs exclusive `end_date`).

**Root cause:** `overdueBase()` summed all PRIN+INT overdue; go-live only floored interest start. No maturity vs go-live skip in calc batch. Booking used raw `end_date` vs EMI due dates instead of interest-accrual `dayBefore(endDate)` pattern.

**Fix (accounting-v2 `feature/delayed_payment_interest`):** Filter dues by `computeOverdueDate < goLive` from base; reader skips `maturity_date < goLiveDate`; `DpiAccrualBookingBatchService.isAccrualPostingDate` mirrors interest accrual.

**Regression:** `ntest run dpic.ud_compliance` — `verify_go_live_ud_e2e.sql`, maturity skip, `verify_dpi_posting_calendar.sql`.

**Prod data:** Historical bad rows need replay/cleanup after deploy; code does not rewrite past accruals.
