#!/usr/bin/env bash
# Local + cron entrypoints for intelligence automations (fast by default).
# Usage:
#   intel-automation.sh session|sync|sync-full|sanity|status|daily|weekly
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

LOG_DIR="$ROOT/.cursor/automations/logs"
mkdir -p "$LOG_DIR"

# Structured run log: utc|job|exit|duration_s — rotate keep last 30 files
_log_run() {
  local job="$1" exit_code="$2" started="$3"
  local ended duration utc logfile
  ended="$(date +%s)"
  duration=$((ended - started))
  utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  logfile="$LOG_DIR/${utc//:/-}_${job}.log"
  printf '%s|%s|%s|%s\n' "$utc" "$job" "$exit_code" "$duration" | tee "$logfile" >/dev/null
  # also append to rolling index
  printf '%s|%s|%s|%s\n' "$utc" "$job" "$exit_code" "$duration" >>"$LOG_DIR/runs.ndjson"
  # rotate: keep newest 30 *.log (exclude runs.ndjson)
  local count
  count="$(find "$LOG_DIR" -maxdepth 1 -type f -name '*.log' | wc -l)"
  if (( count > 30 )); then
    find "$LOG_DIR" -maxdepth 1 -type f -name '*.log' -printf '%T@ %p\n' \
      | sort -n | head -n "$((count - 30))" | awk '{print $2}' | xargs -r rm -f
  fi
}

_run_logged() {
  local job="$1"
  shift
  local started ec
  started="$(date +%s)"
  set +e
  "$@"
  ec=$?
  set -e
  _log_run "$job" "$ec" "$started"
  return "$ec"
}

cmd="${1:-session}"
shift || true

case "$cmd" in
  session)
    exec python3 scripts/testing/sync_engine.py fast-session "$@"
    ;;
  sync)
    exec python3 scripts/testing/sync_engine.py fast-sync "$@"
    ;;
  sync-full)
    exec python3 scripts/testing/super_agent.py sync --full "$@"
    ;;
  sanity)
    exec bash scripts/bin/workspace-sanity.sh --fast "$@"
    ;;
  status)
    exec python3 scripts/testing/sync_engine.py status "$@"
    ;;
  daily)
    # Weekday morning: session + sanity + status + gap miner (target <30s)
    _run_logged daily bash -c '
      set -euo pipefail
      python3 scripts/testing/sync_engine.py fast-session --quiet
      bash scripts/bin/workspace-sanity.sh --fast
      python3 scripts/testing/sync_engine.py status
      python3 scripts/lib/registry_proposals.py mine || true
      python3 -c "from ntest_telemetry import doctor_report, emit_quarantine_proposals; print(doctor_report()); emit_quarantine_proposals()" 2>/dev/null || true
    '
    ;;
  weekly)
    # Heavy: full test intel + bus compact + learning age + SELF-REPORT
    _run_logged weekly bash -c '
      set -euo pipefail
      bash scripts/bin/super-agent.sh sync --full
      python3 scripts/testing/sync_engine.py compact-bus 2>/dev/null || true
      PYTHONPATH=scripts/testing python3 scripts/testing/learn_lifecycle.py age || true
      PYTHONPATH=scripts/testing:scripts/lib python3 scripts/testing/autonomy_loop.py self-report || true
      python3 scripts/lib/registry_proposals.py mine || true
      PYTHONPATH=scripts/lib python3 scripts/lib/process_router.py ratchet || true
      if [[ "${RUN_PLATFORM_SCAN:-0}" == "1" ]]; then
        bash scripts/bin/platform-scan.sh --with-kg
      fi
    '
    ;;
  compact)
    exec python3 scripts/testing/sync_engine.py compact-bus "$@"
    ;;
  *)
    echo "Usage: intel-automation.sh session|sync|sync-full|sanity|status|daily|weekly" >&2
    exit 1
    ;;
esac
