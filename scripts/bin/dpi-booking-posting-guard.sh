#!/usr/bin/env bash
# Static guard: DPI accrual booking posts on month-end OR any EMI INT/PRIN due seal.
# Mirrors calc nextBoundary seals — not this-installment INT only (avoids LIMIT-1 / DPI-due miss).
# Product rule (mfi_integration_v3.7.1 / 77921d275f): prior-EMI slice ending on next EMI due must book.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FILE="$ROOT/trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/DpiAccrualBookingBatchService.java"

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

# New anchor: endDate + preloaded INT/PRIN due-day set (any EMI due), not installment-scoped INT.
if ! grep -qE 'isInstallmentPostingAnchor\(entity\.getEndDate\(\),\s*installmentDueDays\)' "$FILE"; then
  fail "booking must gate on isInstallmentPostingAnchor(endDate, installmentDueDays) — any EMI due seal"
fi

if ! grep -q 'loadInstallmentDueDays' "$FILE"; then
  fail "booking must preload INT/PRIN due days via loadInstallmentDueDays"
fi

if ! grep -q 'getAllActiveLoanDueDetailsByAccId' "$FILE"; then
  fail "due-day preload must reuse getAllActiveLoanDueDetailsByAccId (no LIMIT-1 due lookup)"
fi

# Reject stale installment-INT-only gate (pre-77921d275f).
if grep -qE 'isInstallmentPostingAnchor\(entity\.getInstallmentId\(\)' "$FILE"; then
  fail "stale per-installment INT-only anchor — use loan-level INT/PRIN due-day set"
fi

if grep -qE 'findByLoanInstallmentIdAndComponentType' "$FILE"; then
  fail "stale findByLoanInstallmentIdAndComponentType booking gate — use loadInstallmentDueDays"
fi

if grep -qE 'getLoanDueDetailsForDueDate' "$FILE"; then
  fail "LIMIT-1 getLoanDueDetailsForDueDate must not gate booking (same-day DPI due wins after billing)"
fi

if grep -qE '"PINT"\.equals' "$FILE"; then
  fail "booking must not treat PINT as posting anchor"
fi

echo "dpi-booking-posting-guard: PASS"
