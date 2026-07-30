#!/usr/bin/env bash
# Poll Spring Batch until ONE job_execution_id completes.
# Correlation: bind EXEC_ID at fire time (arg4 / BATCH_JOB_EXECUTION_ID / bind from BEFORE_ID).
# Name+time-window matching is dead — never poll "latest by job name".
set -euo pipefail

JOB_NAME="${1:?job name required}"
JOB_TIME="${2:-}"
# Legacy arg3 was RUN_STARTED epoch; also accepts BEFORE_EXEC_ID when BATCH_WAIT_BEFORE_MODE=1
# Prefer explicit EXEC_ID (arg4) or env BATCH_JOB_EXECUTION_ID.
ARG3="${3:-}"
ARG4="${4:-}"
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
SERVICE_DOWN_FAIL_FAST_S="${BATCH_SERVICE_DOWN_FAIL_FAST_S:-12}"
ABANDON_SQL="$ROOT/scripts/dpic/sql/helpers/dpi_abandon_stuck_batch_jobs.sql"
BIND_TIMEOUT_S="${BATCH_BIND_TIMEOUT_S:-45}"

_booking_floor() {
  case "$JOB_NAME" in
    dpiAccrualBooking|dpiInterestBooking) echo "${BATCH_BOOKING_FLOOR_S:-300}" ;;
    dpiAccrualCalculation|dpiBilling) echo "${BATCH_CALC_FLOOR_S:-180}" ;;
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

max_exec_id() {
  "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" <<'SQL'
SELECT COALESCE(MAX(bje.job_execution_id), 0)::text
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name';
SQL
}

# Bind the FIRST new execution after before_id (MIN, not MAX — concurrent fires must not steal).
bind_exec_id() {
  local before_id="$1"
  local deadline bind_started eid
  bind_started="$(date +%s)"
  deadline=$((bind_started + BIND_TIMEOUT_S))
  while [[ "$(date +%s)" -le "$deadline" ]]; do
    eid="$("${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" -v before_id="$before_id" <<'SQL'
SELECT MIN(bje.job_execution_id)::text
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
  AND bje.job_execution_id > (:'before_id')::bigint;
SQL
)"
    if [[ -n "${eid:-}" && "$eid" =~ ^[0-9]+$ && "$eid" -gt 0 ]]; then
      echo "$eid"
      return 0
    fi
    sleep 0.25
  done
  echo ""
  return 1
}

query_status_by_id() {
  local eid="$1"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v exec_id="$eid" <<'SQL'
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
WHERE bje.job_execution_id = (:'exec_id')::bigint;
SQL
}

started_epoch="$(date +%s)"

if [[ -z "$TIMEOUT_S" ]]; then
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
    dpiAccrualCalculation|dpiBilling) _FLOOR="${BATCH_CALC_FLOOR_S:-180}" ;;
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

_FLOOR="$(_booking_floor)"
if [[ -n "$TIMEOUT_S" && "$TIMEOUT_S" -lt "$_FLOOR" ]]; then
  echo ">>> batch wait floor bump JOB_NAME=$JOB_NAME ${TIMEOUT_S}s → ${_FLOOR}s (env was too low)" >&2
  TIMEOUT_S="$_FLOOR"
fi

# Resolve EXEC_ID — exact row only.
EXEC_ID="${BATCH_JOB_EXECUTION_ID:-${ARG4:-}}"
BEFORE_ID=""
RUN_STARTED=""

if [[ -z "$EXEC_ID" ]]; then
  if [[ -n "${BATCH_BEFORE_EXEC_ID:-}" ]]; then
    BEFORE_ID="$BATCH_BEFORE_EXEC_ID"
  elif [[ -n "$ARG3" && "$ARG3" =~ ^[0-9]+$ ]]; then
    # Heuristic: values that look like epoch (>1e9) are legacy RUN_STARTED;
    # smaller values (or BATCH_WAIT_ARG3=before) are before-exec ids.
    if [[ "${BATCH_WAIT_ARG3:-}" == "before" ]] || [[ "$ARG3" -lt 1000000000 ]]; then
      BEFORE_ID="$ARG3"
    else
      # Legacy epoch: capture max id at wait-start is racy; use create_time bind via BEFORE=max now-1
      # Prefer callers pass before-id. Fallback: bind MIN id with create_time >= epoch (session TZ).
      RUN_STARTED="$ARG3"
      BEFORE_ID="$(max_exec_id)"
      # If job already inserted before we read max, back off one — still use MIN(id)>before after re-read.
      # Safer: set BEFORE to max at fire (caller). Here we re-bind by create_time:
      BEFORE_ID="$(( BEFORE_ID > 0 ? BEFORE_ID - 0 : 0 ))"
    fi
  fi
fi

if [[ -z "$EXEC_ID" ]]; then
  if [[ -n "$RUN_STARTED" ]]; then
    # Bind first row for this job with create_time >= run_started (TZ-aware via epoch extract).
    bind_deadline=$(( $(date +%s) + BIND_TIMEOUT_S ))
    while [[ "$(date +%s)" -le "$bind_deadline" ]]; do
      EXEC_ID="$("${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" -v run_started="$RUN_STARTED" <<'SQL'
SELECT MIN(bje.job_execution_id)::text
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
  AND EXTRACT(EPOCH FROM (bje.create_time AT TIME ZONE current_setting('TimeZone')))::bigint
      >= (:'run_started')::bigint;
SQL
)"
      if [[ -n "${EXEC_ID:-}" && "$EXEC_ID" =~ ^[0-9]+$ ]]; then
        break
      fi
      EXEC_ID=""
      sleep 0.25
    done
  elif [[ -n "$BEFORE_ID" ]]; then
    EXEC_ID="$(bind_exec_id "$BEFORE_ID" || true)"
  fi
fi

if [[ -z "${EXEC_ID:-}" || ! "$EXEC_ID" =~ ^[0-9]+$ ]]; then
  echo ">>> FAIL: could not bind job_execution_id for ${JOB_NAME} (before=${BEFORE_ID:--} run_started=${RUN_STARTED:--} job_time=${JOB_TIME:-})" >&2
  bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
  exit 1
fi

_ship_prog "  … batch-wait ${JOB_NAME} bound exec_id=${EXEC_ID} (budget ${TIMEOUT_S}s)"
echo ">>> ${JOB_NAME} bound exec_id=${EXEC_ID} — polling that row only" >&2

deadline=$((started_epoch + TIMEOUT_S))
next_progress=$((started_epoch + PROGRESS_S))
last_status=""
service_down_since=""

while [[ "$(date +%s)" -le "$deadline" ]]; do
  status="$(query_status_by_id "$EXEC_ID")"
  now="$(date +%s)"
  elapsed=$((now - started_epoch))

  if [[ "$now" -ge "$next_progress" ]]; then
    _ship_prog "  … batch-wait ${JOB_NAME} exec ${EXEC_ID} ${status:-STARTING} ${elapsed}s/${TIMEOUT_S}s"
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
            "$WAIT_SERVICE probe failed while ${JOB_NAME} exec=${EXEC_ID} ${status:-STARTING}" \
            "$elapsed"
        fi
      else
        service_down_since=""
      fi
      ;;
  esac

  case "${status:-}" in
    COMPLETED)
      echo ">>> ${JOB_NAME} COMPLETED exec_id=${EXEC_ID} (${elapsed}s)"
      exit 0
      ;;
    FAILED|STOPPED|ABANDONED)
      echo ">>> ${JOB_NAME} ${status} exec_id=${EXEC_ID} (${elapsed}s)" >&2
      bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
      exit 1
      ;;
    *)
      sleep "$INTERVAL_S"
      ;;
  esac
done

echo ">>> TIMEOUT waiting for ${JOB_NAME} exec_id=${EXEC_ID} (${TIMEOUT_S}s)" >&2
bash "$LOGS" batch "$JOB_NAME" "${JOB_TIME:-}" >&2 || true
exit 1
