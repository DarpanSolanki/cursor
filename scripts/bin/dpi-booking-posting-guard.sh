#!/usr/bin/env bash
# Static guard: DPI accrual booking posts only when slice end_date is this installment's posting anchor.
# Interest parity: month-end or this EMI's INT due — not another EMI's due on the same calendar day.
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

if ! grep -q 'isInstallmentPostingAnchor(entity.getInstallmentId(), entity.getEndDate())' "$FILE"; then
  fail "booking must gate on per-installment posting anchor (end_date = this EMI due or month-end)"
fi

if ! grep -q 'findByLoanInstallmentIdAndComponentType' "$FILE"; then
  fail "per-installment anchor must resolve INT due for installment"
fi

if grep -qE 'isPostingDay\(loanAccountId, businessDate\).*\\|\\|.*isPostingDay\(loanAccountId, entity\.getEndDate\(\)\)' "$FILE"; then
  fail "loan-level businessDate OR end_date gate removed — use per-installment end_date anchor only"
fi

if grep -qE '"PINT"\.equals' "$FILE"; then
  fail "booking must not treat PINT as posting anchor"
fi

echo "dpi-booking-posting-guard: PASS"
