# Lesson: DPI SDCP-10497 false local PASS (2026-06-30)

**What happened:** Agent shipped `6ec669b0e` (gate on `businessDate`) and declared SDCP-10497 fixed after `dpic.ud_compliance` / posting calendar PASS.

**Why false green:**
1. Harness replayed `dpiAccrualBooking` on **EMI due calendar days** (`list_dpi_posting_days.sql`), not BOD day after EOD like QA.
2. `verify_dpi_posting_calendar.sql` was written to match the **wrong** `businessDate` gate.
3. `dpi-booking-posting-guard.sh` **blocked** the correct `dayBefore(end_date)` pattern.
4. Gaps doc marked RESOLVED with inverted evidence text.

**Correct fix:** upstream `accrued_fix` `d479b3a6f` — `dayBefore(exclusive end_date)` + `isFirstDayOfMonth(segStart)` calc split.

**Rule:** DPI money proof requires daily calc+booking EOD replay; never claim QA parity from per-due-day booking replay alone.
