#!/usr/bin/env bash
# Job-first proof: 8060160 June month-end slice via real dpiAccrualCalculation + booking.
# Validates slice integrity after job replay (not static row reads / SQL inserts).
#
# Usage:
#   bash scripts/bin/dpi-june-slice-proof.sh
#   LOAN_ACCOUNT_ID=8060160 END_DATE=2026-06-30 bash scripts/bin/dpi-june-slice-proof.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_pin.sh"
dpi_use_fixture_loan
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-15}"
END_DATE="${END_DATE:-2026-06-30}"
GRACE_DAYS="${GRACE_DAYS:-3}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI June slice job proof loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER ==="
echo "    go_live=$GO_LIVE_ISO calc_through=$END_DATE (real batch jobs only)"

dpi_ensure_accounting ${COMPILE:+--compile}
dpi_ensure_masterdata

read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, 'JLGDL')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"

dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$GO_LIVE_DDMM" -v go_live_sub_type="$product_code" \
  -f "$ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
dpi_evict_go_live_cache "$product_code"
dpi_restart_masterdata
dpi_ensure_accounting ${COMPILE:+--compile}

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

CALENDAR_DAYS="$(
  python3 - "$GO_LIVE_ISO" "$END_DATE" <<'PY'
import sys
from datetime import datetime, timedelta
start = datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
end = datetime.strptime(sys.argv[2], "%Y-%m-%d").date()
d = start
while d <= end:
    print(d.isoformat())
    d += timedelta(days=1)
PY
)"

echo ">>> daily dpiAccrualCalculation + dpiAccrualBooking ($GO_LIVE_ISO .. $END_DATE)"
while IFS= read -r day; do
  [[ -n "$day" ]] || continue
  ms="$(dpi_date_to_ms "$day")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  echo "    EOD $day"
  dpi_call_batch dpiAccrualCalculation "$ms"
  dpi_call_batch dpiAccrualBooking "$ms"
done <<<"$CALENDAR_DAYS"

read -r accrual_rows june_slices <<<"$(
  dpi_pg -t -A -F' ' -c "
SELECT COUNT(*) FILTER (WHERE total_accrued_amount > 0),
       COUNT(*) FILTER (WHERE total_accrued_amount > 0 AND end_date::date = '2026-06-30')
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false;
"
)"
[[ "${accrual_rows:-0}" -gt 0 ]] || fail "no accrual rows after jobs — purge left empty and calc did not run"
[[ "${june_slices:-0}" -gt 0 ]] || fail "no Jun-30 month-end slice after job replay"

echo ""
echo "=== slice integrity (business_date=$END_DATE) ==="
read -r viol rules <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v business_date="$END_DATE" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_accrual_slice_integrity.sql" | head -1
)"
[[ "${viol:-1}" == "0" ]] || fail "slice violations=$viol rules=${rules:-?}"

echo ""
echo "=== June slices (job-generated) ==="
dpi_pg -c "
SELECT start_date::date, end_date::date, total_accrued_amount,
       accrual_posting_date::date AS posted
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = $LOAN_ACCOUNT_ID AND is_deleted = false AND total_accrued_amount > 0
  AND end_date::date >= '2026-06-01' AND end_date::date <= '2026-06-30'
ORDER BY end_date;
"

echo ""
echo "PASS: June slice job proof (rows=$accrual_rows jun30_slices=$june_slices violations=0)"
