#!/usr/bin/env bash
# Canonical log paths + tail/errors helpers for local Novopay services.
set -euo pipefail

_NPL_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$_NPL_ROOT/scripts/lib/novopay-service-lib.sh"

npl_app_log() {
  case "$1" in
    accounting) echo "$_NPL_ROOT/novopay-platform-accounting-v2/logs/mfi/accounting-mfi.log" ;;
    actor) echo "$_NPL_ROOT/novopay-platform-actor/logs/mfi/actor-mfi.log" ;;
    task) echo "$_NPL_ROOT/novopay-platform-task/logs/mfi/task-mfi.log" ;;
    *) return 1 ;;
  esac
}

npl_log_guide() {
  local svc="${1:-accounting}"
  cat <<EOF
Log map for ${svc}:
  app (runtime API/batch):  $(npl_app_log "$svc" 2>/dev/null || echo '?')
  boot (gradle bootRun):    $(nps_boot_log "$svc" 2>/dev/null || echo '?')
  archive:                  $(dirname "$(npl_app_log "$svc")")/archive/

When stuck:
  boot not ready     → novopay-logs.sh boot ${svc}
  API/batch errors   → novopay-logs.sh errors ${svc}
  batch job hanging  → novopay-logs.sh batch <jobName> [job_time_ms]
  one-shot RCA       → novopay-logs.sh snap ${svc}
EOF
}

npl_file_exists() { [[ -f "$1" ]]; }

npl_tail_lines() {
  local file="$1" n="${2:-40}"
  if ! [[ -f "$file" ]]; then
    echo "(missing: $file)"
    return 1
  fi
  tail -n "$n" "$file"
}

npl_grep_errors() {
  local file="$1" n="${2:-25}"
  if ! [[ -f "$file" ]]; then
    echo "(missing: $file)"
    return 1
  fi
  grep -E 'ERROR|FATAL|Exception|BUILD FAILED|Application run failed|NovopayFatal|writeSkipCount|Caused by:' "$file" 2>/dev/null | tail -n "$n" || true
}

npl_boot_phase() {
  local bl="$1"
  if ! [[ -f "$bl" ]]; then
    echo "no-boot-log"
    return 0
  fi
  if grep -qE 'BUILD FAILED|FAILURE: Build failed' "$bl" 2>/dev/null; then
    echo "build-failed"
    return 1
  fi
  if grep -qE 'Application run failed|APPLICATION FAILED TO START' "$bl" 2>/dev/null; then
    echo "app-start-failed"
    return 1
  fi
  if grep -qE 'Started Application in|Tomcat started on port' "$bl" 2>/dev/null; then
    echo "jvm-started"
    return 0
  fi
  if grep -qE '> Task :bootRun' "$bl" 2>/dev/null; then
    echo "bootrun"
    return 0
  fi
  if grep -qE '> Task :compileJava' "$bl" 2>/dev/null; then
    echo "compiling"
    return 0
  fi
  echo "starting"
}

npl_boot_last_line() {
  local bl="$1"
  [[ -f "$bl" ]] || { echo "(no boot log)"; return; }
  tail -1 "$bl" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//' | cut -c1-140
}

npl_gradle_alive() {
  local svc="$1" repo
  repo="$(nps_service_repo "$svc")"
  pgrep -f "${repo}.*bootRun" >/dev/null 2>&1
}

npl_wait_heartbeat() {
  local svc="$1" elapsed="$2" bl phase last
  bl="$(nps_boot_log "$svc")"
  phase="$(npl_boot_phase "$bl" 2>/dev/null || echo failed)"
  last="$(npl_boot_last_line "$bl")"
  echo "  … ${elapsed}s | boot:${phase} | gradle:$([[ "$(npl_gradle_alive "$svc" && echo y || echo n)" == y ]] && echo alive || echo dead) | tail: ${last}"
  echo "     watch: novopay-logs.sh boot ${svc}   app: novopay-logs.sh errors ${svc}"
  if [[ "$phase" == "build-failed" || "$phase" == "app-start-failed" ]]; then
    return 1
  fi
  if [[ "$phase" == failed ]]; then
    return 1
  fi
  if ! npl_gradle_alive "$svc" && [[ "$elapsed" -gt 15 ]]; then
  if ! nps_probe_service "$svc" 2>/dev/null; then
    echo "  WARN: gradle bootRun exited before probe OK — check boot log" >&2
    npl_grep_errors "$bl" 15 >&2 || true
    return 1
  fi
  fi
  return 0
}

npl_snap_service() {
  local svc="${1:-accounting}"
  local app bl
  app="$(npl_app_log "$svc")"
  bl="$(nps_boot_log "$svc")"
  echo "=== snap ${svc} ==="
  nps_status_service "$svc" || true
  echo ""
  echo "app log: $app"
  echo "--- recent errors (app) ---"
  npl_grep_errors "$app" 12 || true
  echo ""
  echo "boot log: $bl"
  echo "--- boot phase: $(npl_boot_phase "$bl" 2>/dev/null || echo failed) ---"
  npl_boot_last_line "$bl"
  echo "--- recent errors (boot) ---"
  npl_grep_errors "$bl" 12 || true
}

npl_batch_status() {
  local job_name="${1:?}" job_time="${2:-}"
  export PGPASSWORD="${PGPASSWORD:-yugabyte}"
  local PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A)
  if [[ -n "$job_time" ]]; then
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$job_name" -v job_time="$job_time" <<'SQL'
SELECT bje.job_execution_id, bje.status, bje.start_time, bje.end_time,
       COALESCE(bje.exit_message,'')
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
JOIN mfi_batch.batch_job_execution_params p ON p.job_execution_id = bje.job_execution_id
WHERE bji.job_name = :'job_name'
  AND p.parameter_name = 'job_time'
  AND p.parameter_value LIKE '%' || :'job_time' || '%'
ORDER BY bje.job_execution_id DESC
LIMIT 3;
SQL
  else
    "${PG[@]}" -v ON_ERROR_STOP=1 -v job_name="$job_name" <<'SQL'
SELECT bje.job_execution_id, bje.status, bje.start_time, bje.end_time,
       COALESCE(bje.exit_message,'')
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = :'job_name'
ORDER BY bje.job_execution_id DESC
LIMIT 3;
SQL
  fi
}

npl_batch_failures() {
  export PGPASSWORD="${PGPASSWORD:-yugabyte}"
  psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -t -A <<'SQL' 2>/dev/null || true
SELECT job_name, failure_reason, created_on
FROM mfi_accounting.batch_failure_audit
ORDER BY id DESC
LIMIT 5;
SQL
}
