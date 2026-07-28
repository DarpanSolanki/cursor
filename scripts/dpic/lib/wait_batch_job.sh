#!/usr/bin/env bash
# Poll Spring Batch until job completes — progress heartbeats + log hints on timeout.
set -euo pipefail

JOB_NAME="${1:?job name required}"
JOB_TIME="${2:-}"
RUN_STARTED="${3:-}"
TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-}"
INTERVAL_S="${BATCH_POLL_INTERVAL_S:-0.5}"
PROGRESS_S="${BATCH_PROGRESS_S:-5}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$ROOT/scripts/bin/novopay-logs.sh"
PROGRESS_LOG="${SHIP_PROGRESS_LOG:-$ROOT/.cursor/ship-progress.log}"

_ship_prog() {
  local line="$1"
  echo "$line"
  mkdir -p "$(dirname "$PROGRESS_LOG")"
  printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$line" >>"$PROGRESS_LOG"
}
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/novopay-service-lib.sh"

PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A)
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

WAIT_SERVICE="${BATCH_WAIT_SERVICE:-accounting}"
# Fail fast when the JVM dies mid-batch (EMF closed) — do not poll until TIMEOUT_S.
SERVICE_DOWN_FAIL_FAST_S="${BATCH_SERVICE_DOWN_FAIL_FAST_S:-12}"
ABANDON_SQL="$ROOT/scripts/dpic/sql/helpers/dpi_abandon_stuck_batch_jobs.sql"

_booking_floor() {
  case "$JOB_NAME" in
    dpiAccrualBooking|dpiInterestBooking) echo "${BATCH_BOOKING_FLOOR_S:-300}" ;;
    *) echo 120 ;;
  esac
}

abandon_hung_dpi_batches() {
  local older="${1:-30}"
  [[ -f "$ABANDON_SQL" ]] || return 0
  "${PG[@]}" -v ON_ERROR_STOP=1 -v older_than_seconds="$older" -f "$ABANDON_SQL" 2>/dev/null \
    | grep -E '^[0-9]+$' | tail -1
}

fail_fast_batch() {
  local reason="$1" elapsed="$2"
  echo ">>> FAIL-FAST (${elapsed}s): $reason" >&2
  local n
  n="$(abandon_hung_dpi_batches 30 || true)"
  if [[ "${n:-0}" =~ ^[1-9] ]]; then
    echo ">>> abandoned $n hung dpi* batch row(s) — restarting $WAIT_SERVICE" >&2
    bash "$ROOT/scripts/bin/novopay-service.sh" restart "$WAIT_SERVICE" >/dev/null 2>&1 || true
  fi
  bash "$LOGS" snap "$WAIT_SERVICE" >&2 || true
  bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
  exit 1
}

started_epoch="$(date +%s)"

if [[ -z "$TIMEOUT_S" ]]; then
  # Derive timeout from recorded history (avoid hard-coded too-short budgets).
  # Budget = max(floor, ceil(3×p50)) from last 10 COMPLETED durations.
  # dpiAccrualBooking on a dirty local portfolio can exceed 90s even when healthy.
  durations="$(
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" <<'SQL'
SELECT ROUND(EXTRACT(EPOCH FROM (bje.end_time - bje.start_time))::numeric, 2)::text AS duration_s
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
  AND bje.status = 'COMPLETED'
  AND bje.start_time IS NOT NULL
  AND bje.end_time IS NOT NULL
ORDER BY bje.job_execution_id DESC
LIMIT 10;
SQL
  )"

  _FLOOR=120
  case "$JOB_NAME" in
    dpiAccrualBooking|dpiInterestBooking) _FLOOR="${BATCH_BOOKING_FLOOR_S:-300}" ;;
  esac

  TIMEOUT_S="$(
    python3 -c 'import math,sys
raw=sys.argv[1]
floor=int(sys.argv[2])
ds=[float(x) for x in raw.split() if x.strip()]
ds=[x for x in ds if x>0]
if not ds:
    print(floor)
else:
    ds=sorted(ds)
    n=len(ds)
    p50 = ds[n//2] if n%2==1 else (ds[n//2-1]+ds[n//2])/2.0
    print(int(max(floor, math.ceil(3.0*p50))))
' "$durations" "$_FLOOR"
  )"
  echo ">>> batch wait budget (derived) JOB_NAME=$JOB_NAME TIMEOUT_S=${TIMEOUT_S}s floor=${_FLOOR}s" >&2
fi

# Env default BATCH_POLL_TIMEOUT_S=90 (dpi_demo_fixture) must not undercut booking floor.
_FLOOR="$(_booking_floor)"
if [[ -n "$TIMEOUT_S" && "$TIMEOUT_S" -lt "$_FLOOR" ]]; then
  echo ">>> batch wait floor bump JOB_NAME=$JOB_NAME ${TIMEOUT_S}s → ${_FLOOR}s (env was too low)" >&2
  TIMEOUT_S="$_FLOOR"
fi

deadline=$((started_epoch + TIMEOUT_S))
next_progress=$((started_epoch + PROGRESS_S))
last_status=""
service_down_since=""

query_status() {
  # Prefer create_time window from ntest run_started (epoch seconds).
  # Do NOT require parameter_name=job_time — many jobs store `time` instead, and
  # correlator JOB_TIME often does not match the value Spring Batch persisted.
  if [[ -n "$RUN_STARTED" ]]; then
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" -v run_started="$RUN_STARTED" <<'SQL'
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
  AND bje.create_time >= to_timestamp((:'run_started')::bigint)
ORDER BY bje.job_execution_id DESC
LIMIT 1;
SQL
  elif [[ -n "$JOB_TIME" ]]; then
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" -v job_time="$JOB_TIME" <<'SQL'
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
WHERE bji.job_name = :'job_name'
  AND p.parameter_name IN ('job_time', 'time')
  AND p.parameter_value = :'job_time'
  AND bje.create_time > NOW() - INTERVAL '30 minutes'
ORDER BY bje.job_execution_id DESC
LIMIT 1;
SQL
  else
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" <<'SQL'
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
  AND bje.create_time > NOW() - INTERVAL '10 minutes'
ORDER BY bje.job_execution_id DESC
LIMIT 1;
SQL
  fi
}

while [[ "$(date +%s)" -le "$deadline" ]]; do
  status="$(query_status)"
  now="$(date +%s)"
  elapsed=$((now - started_epoch))

  if [[ "$now" -ge "$next_progress" && "${status:-}" != "$last_status" ]] || [[ "$now" -ge "$next_progress" ]]; then
    _ship_prog "  … batch-wait ${JOB_NAME} ${status:-STARTING} ${elapsed}s/${TIMEOUT_S}s"
    next_progress=$((now + PROGRESS_S))
  fi
  last_status="${status:-}"

  case "${status:-}" in
    STARTED|STARTING|UNKNOWN|"")
      if ! nps_probe_service "$WAIT_SERVICE" 2>/dev/null; then
        if [[ -z "$service_down_since" ]]; then
          service_down_since="$now"
        elif (( now - service_down_since >= SERVICE_DOWN_FAIL_FAST_S )); then
          fail_fast_batch \
            "$WAIT_SERVICE probe failed while ${JOB_NAME} ${status:-STARTING} (JVM likely crashed — check EntityManagerFactory is closed)" \
            "$elapsed"
        fi
      else
        service_down_since=""
      fi
      ;;
  esac

  case "${status:-}" in
    COMPLETED)
      echo ">>> ${JOB_NAME} COMPLETED (${elapsed}s)"
      exit 0
      ;;
    FAILED|STOPPED|ABANDONED)
      echo ">>> ${JOB_NAME} ${status} (${elapsed}s)" >&2
      bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
      exit 1
      ;;
    STARTED|STARTING|UNKNOWN|"")
      sleep "$INTERVAL_S"
      ;;
    *)
      sleep "$INTERVAL_S"
      ;;
  esac
done

echo ">>> TIMEOUT waiting for ${JOB_NAME} (${TIMEOUT_S}s)" >&2
bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
exit 1
