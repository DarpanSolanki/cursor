#!/usr/bin/env bash
# Shared helpers for DPIC QA presentation steps.
set -euo pipefail

_DEMO_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DEMO_ROOT="$(cd "$_DEMO_LIB_DIR/../../../.." && pwd)"

source "$_DEMO_LIB_DIR/../demo_config.env"
# shellcheck disable=SC1091
source "$_DEMO_LIB_DIR/demo_runtime.sh"

# Anchor timeline (EMI 14th; presentation day default 15-Jun-2026).
eval "$(python3 "$_DEMO_LIB_DIR/compute_dates.py" --anchor "${DEMO_ANCHOR:-2026-06-15}")"

export ROOT="$_DEMO_ROOT"
export STATE_FILE="${STATE_FILE:-$ROOT/$DEMO_STATE_FILE}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
NTEST="$ROOT/scripts/bin/ntest.sh"

demo_banner() {
  echo ""
  echo "================================================================"
  echo "  $*"
  echo "================================================================"
  echo ""
}

demo_pause() {
  if [[ "${INTERACTIVE:-0}" == "1" ]]; then
    read -rp ">>> Press Enter to continue..."
    echo ""
  fi
}

demo_require_service() {
  local base="${ACCOUNTING_BASE_URL:-http://localhost:8002}"
  local code
  code="$(curl -s -o /dev/null -w '%{http_code}' "${base}/actuator/health" 2>/dev/null || echo 000)"
  if [[ "$code" != "200" ]]; then
    echo "WARN: accounting health at ${base}/actuator/health returned ${code} (expected 200)" >&2
  fi
}

demo_load_state() {
  if [[ -f "$STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    set -a && source "$STATE_FILE" && set +a
  fi
}

demo_save_state_kv() {
  mkdir -p "$(dirname "$STATE_FILE")"
  touch "$STATE_FILE"
  local key="$1" val="$2"
  if grep -q "^${key}=" "$STATE_FILE" 2>/dev/null; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$STATE_FILE"
  else
    echo "${key}=${val}" >>"$STATE_FILE"
  fi
}

demo_resolve_loan() {
  : "${EXT_REF:?Set EXT_REF or run step_01_disburse.sh first}"
  read -r LOAN_ACCOUNT_ID LAN LOAN_STATUS PAST_DUE FIRST_EMI <<<"$(
    "${PG[@]}" -t -A -F' ' -v ON_ERROR_STOP=1 -v ext_ref="$EXT_REF" <<'SQL'
SELECT la.account_id, a.account_number, la.loan_status, la.past_due_days,
       (SELECT MIN(lid.installment_date)::text
        FROM mfi_accounting.loan_installment_details lid
        WHERE lid.loan_account_id = la.account_id AND lid.is_deleted = false)
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE la.external_ref_number LIKE :'ext_ref' || '%'
  AND la.is_deleted = false
ORDER BY la.account_id DESC
LIMIT 1;
SQL
  )"
  if [[ -z "${LOAN_ACCOUNT_ID:-}" ]]; then
    echo "FAIL: no loan for ext_ref prefix $EXT_REF" >&2
    exit 1
  fi
  export LOAN_ACCOUNT_ID LAN LOAN_STATUS PAST_DUE FIRST_EMI
  demo_save_state_kv ACCOUNT_NUMBER "$LAN"
  demo_save_state_kv LOAN_ACCOUNT_ID "$LOAN_ACCOUNT_ID"
}

demo_run_eod() {
  local job_time="$1"
  local label="${2:-EOD}"
  demo_banner "$label — job_time=$job_time ($(date -d "@$((job_time / 1000))" '+%d-%b-%Y %H:%M' 2>/dev/null || echo epoch))"
  demo_require_service
  : "${LOAN_ACCOUNT_ID:?}"
  LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="$job_time" SEED_CALC_WINDOW="${SEED_CALC_WINDOW:-0}" \
    bash "$ROOT/scripts/dpic/run_eod.sh"
}

demo_show_dpi_status() {
  : "${LOAN_ACCOUNT_ID:?}"
  demo_banner "DPI status snapshot (loan_account_id=$LOAN_ACCOUNT_ID)"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -f "$ROOT/scripts/dpic/demo/sql/demo_status.sql"
  echo ""
}

demo_talking_points() {
  echo "--- What to tell QA ---"
  while (($#)); do echo "  • $1"; shift; done
  echo ""
}
