#!/usr/bin/env bash
# Static guard: DPI accrual booking must gate on slice end (dayBefore exclusive end_date),
# NOT on EOD businessDate for EMI due — SDCP-10497 / upstream accrued_fix.
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
  fail "EMI posting gated on businessDate/postingDate — must use dayBefore(sliceEndDate)"
fi

if ! grep -qE 'dayBefore\(sliceEndDate\)|Date lastAccruedDay = dayBefore' "$FILE"; then
  fail "missing dayBefore(sliceEndDate) posting gate"
fi

if ! grep -q 'isAccrualPostingDate(entity.getEndDate()' "$FILE"; then
  fail "isEligible must call isAccrualPostingDate(entity.getEndDate(), ...)"
fi

if ! grep -q 'entity.getEndDate().after(businessDate)' "$FILE"; then
  fail "missing end_date <= businessDate eligibility check"
fi

if ! grep -q 'dayBefore(entity.getEndDate())' "$FILE"; then
  fail "value_date must use dayBefore(entity.getEndDate()) for GL accrual date"
fi

echo "dpi-booking-posting-guard: PASS"
