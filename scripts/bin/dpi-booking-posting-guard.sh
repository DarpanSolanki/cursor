#!/usr/bin/env bash
# Static guard: DPI accrual booking must only post on posting anchors (EMI PRIN/INT due or month-end).
# Booking may run with EOD job_time (businessDate) and must allow either:
# - slice end_date is a posting anchor, OR
# - businessDate is a posting anchor (e.g. due-day EOD), while still enforcing end_date <= businessDate.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FILE="$ROOT/novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/DpiAccrualBookingBatchService.java"

if [[ ! -f "$FILE" ]]; then
  echo "dpi-booking-posting-guard: SKIP (no DpiAccrualBookingBatchService on disk)" >&2
  exit 0
fi

fail() {
  echo "dpi-booking-posting-guard FAIL: $*" >&2
  exit 1
}

if grep -qE 'dueDayKeys\.contains\(truncateToDayMillis\(postingDate\)\)' "$FILE"; then
  fail "legacy dueDayKeys businessDate gate detected (unexpected in current design)"
fi

if ! grep -qE 'entity\.getEndDate\(\)\.after\(businessDate\)' "$FILE"; then
  fail "missing end_date <= businessDate eligibility check"
fi

if ! grep -qE 'isPostingDay\(loanAccountId, businessDate\).*\\|\\|.*isPostingDay\(loanAccountId, entity\.getEndDate\(\)\)' "$FILE"; then
  fail "posting anchor gate must allow businessDate OR slice end_date"
fi

if ! grep -q 'getLoanDueDetailsForDueDate(' "$FILE"; then
  fail "isPostingDay must consult due_date rows (PRIN/INT)"
fi

if grep -qE '"PINT"\.equals' "$FILE"; then
  fail "booking must not treat PINT as posting anchor"
fi

echo "dpi-booking-posting-guard: PASS"
