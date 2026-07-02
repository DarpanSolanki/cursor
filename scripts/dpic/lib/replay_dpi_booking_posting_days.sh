#!/usr/bin/env bash
# Replay dpiAccrualBooking on each EMI/month-end day through business_date (after calc).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${1:?loan_account_id}"
JOB_TIME_MS="${2:?job_time_ms}"
GO_LIVE_ISO="${3:-}"

date_to_ms() {
  python3 - "$1" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
d = datetime.strptime(sys.argv[1], "%Y-%m-%d")
ist = timezone(timedelta(hours=5, minutes=30))
print(int(d.replace(tzinfo=ist).timestamp() * 1000))
PY
}

business_date="$(python3 - "$JOB_TIME_MS" <<'PY'
import sys
from datetime import datetime, timezone, timedelta
ms = int(sys.argv[1])
ist = timezone(timedelta(hours=5, minutes=30))
print(datetime.fromtimestamp(ms / 1000, ist).strftime("%Y-%m-%d"))
PY
)"

if [[ -z "$GO_LIVE_ISO" ]]; then
  GO_LIVE_ISO="$(dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(
  (SELECT MIN(start_date::date)::text
   FROM mfi_accounting.dpi_accrual_details
   WHERE loan_account_id = :loan_account_id::bigint
     AND is_deleted = false
     AND total_accrued_amount > 0),
  '2025-04-15'
);
SQL
)"
fi

NTEST="$ROOT/scripts/bin/ntest.sh"
WAIT_BATCH="$ROOT/scripts/dpic/lib/wait_batch_job.sh"

purge_batch() {
  dpi_pg -v ON_ERROR_STOP=1 -v job_name="dpiAccrualBooking" -v job_time="$1" \
    -f "$ROOT/scripts/dpic/sql/helpers/purge_batch_job_execution.sql" >/dev/null
}

POSTING_DAYS="$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v go_live_date="$GO_LIVE_ISO" \
    -v end_date="$business_date" \
    -f "$ROOT/scripts/dpic/sql/helpers/list_dpi_posting_days.sql"
)"

while IFS= read -r day; do
  [[ -n "$day" ]] || continue
  ms="$(date_to_ms "$day")"
  purge_batch "$ms"
  rs="$(date +%s)"
  JOB_TIME="$ms" "$NTEST" api accounting dpiAccrualBooking --batch --job-time "$ms" >/dev/null
  bash "$WAIT_BATCH" dpiAccrualBooking "$ms" "$rs"
done <<<"$POSTING_DAYS"
