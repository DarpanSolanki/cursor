#!/usr/bin/env bash
# Shared DPI demo-loan fixture — canonical IDs in lib/dpi_fixture_constants.sh
set -euo pipefail

_DPI_FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DPI_FIXTURE_ROOT="$(cd "$_DPI_FIXTURE_DIR/../../.." && pwd)"
# shellcheck disable=SC1091
source "$_DPI_FIXTURE_DIR/dpi_fixture_constants.sh"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-$DPI_FIXTURE_LOAN_ID}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-$DPI_FIXTURE_LAN}"
export DEMO_LAN="${DEMO_LAN:-$ACCOUNT_NUMBER}"
export JOB_TIME="${JOB_TIME:-$DPI_FIXTURE_JOB_TIME}"
export FORECLOSURE_DATE="${FORECLOSURE_DATE:-1784984400000}"
export GRACE_DAYS="${GRACE_DAYS:-3}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

dpi_pg() {
  psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" "$@"
}

dpi_export_correlators() {
  export ACCOUNT_NUMBER DEMO_LAN LOAN_ACCOUNT_ID JOB_TIME FORECLOSURE_DATE
  python3 - "$DPI_FIXTURE_ROOT/scripts/testing/registry.json" <<'PY'
import json, os, sys
from pathlib import Path
reg = Path(sys.argv[1])
data = json.loads(reg.read_text(encoding="utf-8"))
c = data.setdefault("_correlators", {})
for k in ("ACCOUNT_NUMBER", "LOAN_ACCOUNT_ID", "JOB_TIME", "FORECLOSURE_DATE", "DEMO_LAN"):
    v = os.environ.get(k)
    if v:
        c[k] = str(v)
reg.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
}

dpi_restore_api_state() {
  LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" JOB_TIME="$JOB_TIME" \
    bash "$DPI_FIXTURE_ROOT/scripts/dpic/restore_dpi_api_state.sh"
}

dpi_ensure_accounting() {
  bash "$DPI_FIXTURE_ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}
}

dpi_probe_masterdata() {
  local code
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST \
    "http://127.0.0.1:8014/masterdata/api/v1/getBulkUniqueMasterData" \
    -H 'Content-Type: application/json' \
    -d '{"headers":{"tenant_code":"mfi","user_id":"3","stan":"md_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"query_list":[{"datatype":"TEST","datasubtype":"TEST","data_code":"TEST"}]}}' \
    2>/dev/null || echo 000)"
  [[ "$code" == "200" ]]
}

dpi_ensure_masterdata() {
  if dpi_probe_masterdata; then
    echo "  masterdata: probe OK on :8014"
    return 0
  fi
  echo "  masterdata: starting on :8014..."
  local bl="$DPI_FIXTURE_ROOT/scripts/scratch/services/masterdata-bootrun.log"
  mkdir -p "$(dirname "$bl")"
  : >"$bl"
  (
    cd "$DPI_FIXTURE_ROOT/trustt-platform-masterdata-management"
    nohup ./gradlew bootRun >>"$bl" 2>&1 &
    echo $! >"$DPI_FIXTURE_ROOT/scripts/scratch/services/masterdata.pid"
  )
  local i
  for i in $(seq 1 36); do
    if dpi_probe_masterdata; then
      echo "  masterdata: ready (${i}*5s)"
      return 0
    fi
    sleep 5
  done
  echo "FAIL: masterdata not ready on :8014" >&2
  tail -20 "$bl" >&2 || true
  return 1
}

dpi_ensure_actor() {
  # shellcheck disable=SC1091
  source "$DPI_FIXTURE_ROOT/scripts/lib/novopay-service-lib.sh"
  nps_probe_service actor 2>/dev/null || bash "$DPI_FIXTURE_ROOT/scripts/bin/novopay-service.sh" ensure actor
}

dpi_job_time_repay_ms() {
  python3 - "$JOB_TIME" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
ms = int(sys.argv[1])
ist = timezone(timedelta(hours=5, minutes=30))
d = datetime.fromtimestamp(ms / 1000, ist).replace(hour=18, minute=0, second=0, microsecond=0)
print(int(d.timestamp() * 1000))
PY
}

dpi_job_time_anchor_date() {
  python3 - "$JOB_TIME" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
ms = int(sys.argv[1])
ist = timezone(timedelta(hours=5, minutes=30))
print(datetime.fromtimestamp(ms / 1000, ist).strftime("%Y-%m-%d"))
PY
}

dpi_assert_sql_eq() {
  local sql="$1" expected="$2" label="$3"
  local got
  got="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c "$sql" 2>/dev/null | tr -d '[:space:]')"
  if [[ "$got" != "$expected" ]]; then
    echo "FAIL: $label — got '$got' expected '$expected'" >&2
    return 1
  fi
  echo "OK: $label ($got)"
}

dpi_assert_sql_gt() {
  local sql="$1" min="$2" label="$3"
  local got
  got="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -c "$sql" 2>/dev/null | tr -d '[:space:]')"
  python3 - "$got" "$min" "$label" <<'PY'
import sys
got, min_s, label = sys.argv[1:4]
try:
    g, m = float(got), float(min_s)
except ValueError:
    print(f"FAIL: {label} — non-numeric got={got}", file=sys.stderr)
    sys.exit(1)
if g <= m:
    print(f"FAIL: {label} — {g} not > {m}", file=sys.stderr)
    sys.exit(1)
print(f"OK: {label} ({got} > {min_s})")
PY
}

dpi_evict_go_live_cache() {
  local product_code="${1:-}"
  echo "  dpi: evict go-live cache (product=${product_code:-*}) — restart accounting"
  bash "$DPI_FIXTURE_ROOT/scripts/bin/novopay-service.sh" ensure accounting --compile 2>/dev/null \
    || bash "$DPI_FIXTURE_ROOT/scripts/bin/novopay-service.sh" ensure accounting
}

# Args: go_live_ddmm (DD-MM-YYYY) product_code (code_master data_sub_type)
dpi_set_go_live_and_refresh() {
  local go_live_ddmm="${1:?go_live DD-MM-YYYY}"
  local product_code="${2:?product code}"
  echo "  dpi: set DPI_GO_LIVE_DATE=$go_live_ddmm product=$product_code"
  dpi_pg -v ON_ERROR_STOP=1 -v go_live_value="$go_live_ddmm" -v go_live_sub_type="$product_code" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/upsert_dpi_go_live.sql" >/dev/null
  dpi_evict_go_live_cache "$product_code"
  dpi_restart_masterdata
  dpi_ensure_accounting
}

dpi_restart_masterdata() {
  echo "  dpi: restart masterdata (refresh bulk master go-live)"
  dpi_ensure_masterdata
}

# Canonical local batch trigger — same path as QA/prod (ntest → gateway → Spring Batch).
dpi_date_to_ms() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
d = datetime.strptime(sys.argv[1], "%Y-%m-%d")
ist = timezone(timedelta(hours=5, minutes=30))
print(int(d.replace(tzinfo=ist).timestamp() * 1000))
PY
}

dpi_purge_batch() {
  local job_name="$1" job_time="$2"
  dpi_pg -v ON_ERROR_STOP=1 -v job_name="$job_name" -v job_time="$job_time" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
}

# Abandon hung dpi* STARTED rows left by prior TIMEOUT (default: older than 3 minutes).
# Never use a short window here — that races the in-flight job dpi_call_batch is waiting on.
# Returns count abandoned via stdout (for restart decision).
dpi_abandon_stuck_batches() {
  local older="${1:-180}"
  # -t -A: UPDATE emits no row, final SELECT emits just the integer count.
  # awk on the aligned header returned the literal word "abandoned" (never a number),
  # so restart never fired — parse the numeric tuple only.
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v older_than_seconds="$older" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/dpi_abandon_stuck_batch_jobs.sql" 2>/dev/null \
    | grep -E '^[0-9]+$' | tail -1
}

# DB FAILED does not stop the JVM TenantTaskAsynExec — restart accounting when we abandon.
dpi_restart_accounting_if_abandoned() {
  local n="${1:-0}"
  if [[ "${n:-0}" =~ ^[1-9] ]]; then
    echo "  dpi: abandoned $n stuck batch(es) — restart accounting to clear JVM workers"
    bash "$DPI_FIXTURE_ROOT/scripts/bin/novopay-service.sh" restart accounting >/dev/null
  fi
}

# Usage: dpi_call_batch dpiAccrualCalculation [job_time_ms] [purge=1]
# QA path: ntest batch API + wait_batch_job.sh (same as registry batch.dpi_* intent).
dpi_call_batch() {
  local api="$1" job_time="${2:-$JOB_TIME}" purge="${3:-1}"
  local rs wait="$DPI_FIXTURE_ROOT/scripts/dpic/lib/wait_batch_job.sh"
  local ntest="$DPI_FIXTURE_ROOT/scripts/bin/ntest.sh"
  # Matrix hops can exceed 25s under YB contention — default higher for harness fires.
  export BATCH_POLL_TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-90}"
  # Purge same job_time only — do NOT abandon other in-flight dpi jobs (that kills siblings).
  [[ "$purge" == "1" ]] && dpi_purge_batch "$api" "$job_time"
  rs="$(date +%s)"
  echo ">>> ${api} job_time=${job_time}"
  echo "# QA: JOB_TIME=$job_time bash scripts/bin/ntest.sh api accounting $api --batch --job-time $job_time"
  echo "# QA: bash scripts/dpic/lib/wait_batch_job.sh $api $job_time $rs"
  JOB_TIME="$job_time" "$ntest" api accounting "$api" --batch --job-time "$job_time" >/dev/null
  bash "$wait" "$api" "$job_time" "$rs"
}

dpi_call_eod_chain() {
  local job_time="${1:-$JOB_TIME}"
  dpi_call_batch dpiAccrualCalculation "$job_time"
  dpi_call_batch dpiAccrualBooking "$job_time"
  dpi_call_batch dpiBilling "$job_time"
}

# Per-case isolation on a shared fixture LAN: wipe accrual/DPI residue, restore schedule,
# reset booking-replay flags. Call at the start of every grace-chain scenario so two_emi /
# overlap / booking_anchor cannot stomp each other via soft-deleted EMI3+ or sealed_unbilled leftover.
dpi_isolate_loan_for_case() {
  local loan_id="${1:-${LOAN_ACCOUNT_ID:?LOAN_ACCOUNT_ID required}}"
  local abandoned
  echo "  dpi: isolate loan=$loan_id (hard purge accruals + restore installments)"
  # Clear only truly stuck prior runs (>3 min). Restart JVM if any were abandoned.
  abandoned="$(dpi_abandon_stuck_batches 180 || true)"
  dpi_restart_accounting_if_abandoned "${abandoned:-0}"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/hard_purge_dpi_accruals_for_loan.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" <<'SQL' >/dev/null
UPDATE mfi_accounting.loan_due_details
SET is_deleted = true, updated_on = NOW(), updated_by = 'DPI_CASE_ISOLATE'
WHERE loan_account_id = :loan_account_id::bigint
  AND component_type = 'DPI' AND is_deleted = false;
SQL
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/restore_grace_chain_installments.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$loan_id" \
    -f "$DPI_FIXTURE_ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null 2>&1 || true
}
