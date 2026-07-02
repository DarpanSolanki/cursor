#!/usr/bin/env bash
# Shared DPI demo-loan fixture (8060160 / 6004044425) for ntest + E2E scripts.
set -euo pipefail

_DPI_FIXTURE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DPI_FIXTURE_ROOT="$(cd "$_DPI_FIXTURE_DIR/../../.." && pwd)"

export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export DEMO_LAN="${DEMO_LAN:-$ACCOUNT_NUMBER}"
export JOB_TIME="${JOB_TIME:-1782563400000}"
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
    cd "$DPI_FIXTURE_ROOT/novopay-platform-masterdata-management"
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
