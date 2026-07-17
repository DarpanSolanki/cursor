#!/usr/bin/env bash
# Poll Spring Batch until job completes — progress heartbeats + log hints on timeout.
set -euo pipefail

JOB_NAME="${1:?job name required}"
JOB_TIME="${2:-}"
RUN_STARTED="${3:-}"
TIMEOUT_S="${BATCH_POLL_TIMEOUT_S:-25}"
INTERVAL_S="${BATCH_POLL_INTERVAL_S:-0.5}"
PROGRESS_S="${BATCH_PROGRESS_S:-5}"

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
LOGS="$ROOT/scripts/bin/novopay-logs.sh"

PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A)
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

started_epoch="$(date +%s)"
deadline=$((started_epoch + TIMEOUT_S))
next_progress=$((started_epoch + PROGRESS_S))
last_status=""

query_status() {
  if [[ -n "$JOB_TIME" && -n "$RUN_STARTED" ]]; then
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$JOB_NAME" -v job_time="$JOB_TIME" -v run_started="$RUN_STARTED" <<'SQL'
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
WHERE bji.job_name = :'job_name'
  AND p.parameter_name = 'job_time'
  AND p.parameter_value = :'job_time'
  AND bje.create_time > NOW() - INTERVAL '30 minutes'
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
  AND p.parameter_name = 'job_time'
  AND p.parameter_value = :'job_time'
  AND bje.create_time > NOW() - INTERVAL '10 minutes'
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
    echo "  … ${JOB_NAME} ${status:-STARTING} (${elapsed}s) — novopay-logs.sh errors accounting"
    next_progress=$((now + PROGRESS_S))
  fi
  last_status="${status:-}"

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
