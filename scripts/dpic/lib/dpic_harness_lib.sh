#!/usr/bin/env bash
# DPIC harness intelligence — platform date, safe repay amounts, API contract asserts.
# Sourced by demo_runtime.sh and dpi E2E scripts. No product code here.
set -euo pipefail

_DPIC_HARNESS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DPIC_HARNESS_ROOT="$(cd "$_DPIC_HARNESS_DIR/../../.." && pwd)"

# --- Platform business date (loanRepayment / reversal / part-prep) ---
# Rule: transaction timestamps MUST match SetCommonAttributesProcessor value_date
# (platform "today"), NOT fixture JOB_TIME. JOB_TIME is for batch EOD only.
dpic_platform_repay_ms() {
  python3 - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
d = datetime.now(ZoneInfo("Asia/Kolkata")).replace(hour=18, minute=0, second=0, microsecond=0)
print(int(d.timestamp() * 1000))
PY
}

dpic_platform_business_date() {
  python3 - <<'PY'
from datetime import datetime
from zoneinfo import ZoneInfo
print(datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%Y-%m-%d"))
PY
}

dpic_repayment_timestamps() {
  export REPAY_MS="$(dpic_platform_repay_ms)"
  export REPAY_DATE="$(dpic_platform_business_date)"
}

# Cap avoids 134243 (repayment > unsettled + advance EMI slots). Override: DPI_REPAY_CAP.
dpic_compute_safe_repay_amount() {
  local loan_id="${1:?loan_account_id}"
  local anchor="${2:?anchor_date YYYY-MM-DD}"
  local cap="${DPI_REPAY_CAP:-2000}"
  local pg_cmd=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
    -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A -v ON_ERROR_STOP=1)
  "${pg_cmd[@]}" -v loan_account_id="$loan_id" -v anchor_date="$anchor" -v repay_cap="$cap" \
    -f "$DPIC_HARNESS_ROOT/scripts/dpic/sql/helpers/compute_safe_loan_repayment_amount.sql"
}

# Overview omits dpi_paid_amount / dpi_waived_amount when no DPI due rows — assert via SQL.
dpic_assert_lapd_dpi_paid_gt() {
  local loan_id="${1:?}"
  local min="${2:-0}"
  local pg_cmd=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" \
    -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A -v ON_ERROR_STOP=1)
  local got
  got="$("${pg_cmd[@]}" -c \
    "SELECT COALESCE(MAX(dpi_amount),0)::text FROM mfi_accounting.loan_account_payments_details WHERE loan_account_id=${loan_id} AND COALESCE(is_deleted,false)=false")"
  python3 - "$got" "$min" <<'PY'
import sys
g, m = float(sys.argv[1] or 0), float(sys.argv[2])
if g <= m:
    print(f"FAIL: lapd.dpi_amount {g} not > {m}", file=sys.stderr)
    sys.exit(1)
print(f"OK: lapd max dpi_amount={sys.argv[1]}")
PY
}

dpic_assert_overview_dpi_overdue_eq() {
  local expected="${1:-0}"
  local account="${ACCOUNT_NUMBER:-${LAN:-}}"
  : "${account:?ACCOUNT_NUMBER required}"
  if command -v demo_assert_api_field_eq >/dev/null 2>&1; then
    demo_assert_api_field_eq getLoanAccountOverviewDetails \
      "account_overview_list[0].amount_details.dpi_overdue_amount" "$expected"
  else
    echo "WARN: demo_assert_api_field_eq unavailable — skip overview dpi_overdue assert"
  fi
}

# Preflight: fail fast with harness diagnosis (not product mystery).
dpic_harness_preflight() {
  local loan_id="${LOAN_ACCOUNT_ID:-}"
  local lan="${ACCOUNT_NUMBER:-}"
  local fail=0
  echo ">>> dpic harness preflight (loan=$loan_id LAN=$lan)"
  bash "$DPIC_HARNESS_ROOT/scripts/bin/novopay-service.sh" ensure accounting >/dev/null || fail=1
  if [[ -n "$loan_id" ]]; then
    local st
  st="$(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" \
      -d "${YB_DB:-yugabyte}" -t -A -v ON_ERROR_STOP=1 -c \
      "SELECT loan_status FROM mfi_accounting.loan_account WHERE account_id=${loan_id} AND COALESCE(is_deleted,false)=false" 2>/dev/null || echo "")"
    if [[ "$st" != "ACTIVE" ]]; then
      echo "FAIL: harness preflight — loan $loan_id status='$st' (need ACTIVE)" >&2
      fail=1
    fi
  fi
  echo "  platform_date=$(dpic_platform_business_date) repay_ms=$(dpic_platform_repay_ms)"
  echo "  fixture JOB_TIME=${JOB_TIME:-unset} (batch only — not for loanRepayment timestamps)"
  [[ "$fail" == "0" ]] || return 1
  echo "  preflight OK"
}

# Fail-fast wall clock for E2E scripts (override: DPI_E2E_TIMEOUT_S=300).
dpic_e2e_timeout() {
  local secs="${DPI_E2E_TIMEOUT_S:-120}"
  if command -v timeout >/dev/null 2>&1; then
    timeout --foreground "$secs" "$@"
  else
    "$@"
  fi
}

dpic_harness_hint_for_code() {
  local code="${1:-}"
  case "$code" in
    132280) echo "HARNESS: repayment_time/value_date must be platform today (dpic_platform_repay_ms), not JOB_TIME" ;;
    134243) echo "HARNESS: repayment amount too high vs advance-EMI guard — use dpic_compute_safe_repay_amount or lower DPI_REPAY_CAP" ;;
    130241) echo "HARNESS: request must match JTF nest (e.g. loan_account_part_prepayment.{loan_account_number,...})" ;;
    134207) echo "HARNESS: NPA/asset slab — force_regular_asset_slab or use non-NPA fixture LAN" ;;
    *) echo "Check product + logs; if registry-only assert failed, verify API contract vs path_exists" ;;
  esac
}
