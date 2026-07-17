#!/usr/bin/env bash
# Run DPI calc+booking at milestone dates (QA jumps business date) — not every calendar day.
# Usage:
#   dpi_run_milestone_eod.sh single 2026-06-02          # one jump to end (fastest QA shape)
#   dpi_run_milestone_eod.sh milestones 2026-03-15 2026-06-02  # EMI due + month-end hops
# Env: LOAN_ACCOUNT_ID, GO_LIVE_ISO, END_DATE, ROOT (set by caller)
set -euo pipefail

MODE="${1:?mode: single|milestones}"
shift || true

ROOT="${ROOT:?ROOT required}"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:?LOAN_ACCOUNT_ID required}"
NTEST="${NTEST:-$ROOT/scripts/bin/ntest.sh}"
WAIT_BATCH="${WAIT_BATCH:-$ROOT/scripts/dpic/lib/wait_batch_job.sh}"

date_to_ms() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
d = datetime.strptime(sys.argv[1], "%Y-%m-%d")
ist = timezone(timedelta(hours=5, minutes=30))
print(int(d.replace(tzinfo=ist).timestamp() * 1000))
PY
}

purge_batch() {
  dpi_pg -v ON_ERROR_STOP=1 -v job_name="$1" -v job_time="$2" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
}

call_batch() {
  # Prefer shared harness (abandon stuck + 90s poll + purge) over local wait-only.
  dpi_call_batch "$1" "$2"
}

run_eod_at() {
  local day="$1"
  local ms
  ms="$(date_to_ms "$day")"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date_ms="$ms" \
    -f "$ROOT/scripts/dpic/sql/helpers/sync_demo_past_due.sql" >/dev/null
  echo "    EOD jump → $day"
  call_batch dpiAccrualCalculation "$ms"
  call_batch dpiAccrualBooking "$ms"
}

resolve_milestone_days() {
  local go_live="$1" end_date="$2"
  if [[ "$MODE" == "single" ]]; then
    echo "$end_date"
    return 0
  fi
  dpi_pg -t -A -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v go_live_date="$go_live" \
    -v end_date="$end_date" \
    -f "$ROOT/scripts/dpic/sql/helpers/list_dpi_posting_days.sql"
  echo "$end_date"
}

GO_LIVE_ISO="${GO_LIVE_ISO:-2026-03-15}"
END_DATE="${END_DATE:-2026-06-02}"

case "$MODE" in
  single)
    END_DATE="${1:-$END_DATE}"
  ;;
  milestones)
    GO_LIVE_ISO="${1:-$GO_LIVE_ISO}"
    END_DATE="${2:-$END_DATE}"
  ;;
  *)
    echo "unknown mode: $MODE" >&2
    exit 1
  ;;
esac

mapfile -t DAYS < <(resolve_milestone_days "$GO_LIVE_ISO" "$END_DATE" | sort -u)

echo ">>> DPI milestone EOD mode=$MODE loan=$LOAN_ACCOUNT_ID hops=${#DAYS[@]} ($GO_LIVE_ISO .. $END_DATE)"
for day in "${DAYS[@]}"; do
  [[ -n "$day" ]] || continue
  run_eod_at "$day"
done

FINAL_MS="$(date_to_ms "$END_DATE")"
echo ">>> billing on $END_DATE"
call_batch dpiBilling "$FINAL_MS"
