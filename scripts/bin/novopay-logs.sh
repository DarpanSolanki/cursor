#!/usr/bin/env bash
# Local log discovery — agents never guess paths; use on stuck boot/batch/API.
#
#   novopay-logs.sh paths [accounting|actor|task]
#   novopay-logs.sh tail   <service> [lines]
#   novopay-logs.sh errors <service> [lines]
#   novopay-logs.sh boot   <service> [lines]
#   novopay-logs.sh snap   [service]
#   novopay-logs.sh batch  <jobName> [job_time_ms]
#   novopay-logs.sh guide  [service]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/novopay-logs-lib.sh"

usage() {
  sed -n '2,11p' "$0"
  exit "${1:-0}"
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" || -z "${1:-}" ]] && usage 0

cmd="$1"
shift

case "$cmd" in
  paths|guide)
    npl_log_guide "${1:-accounting}"
    ;;
  tail|errors|boot)
    svc="${1:-accounting}"
    n_lines="${2:-40}"
    case "$cmd" in
      tail) npl_tail_lines "$(npl_app_log "$svc")" "$n_lines" ;;
      errors)
        echo "# $(npl_app_log "$svc")"
        npl_grep_errors "$(npl_app_log "$svc")" "$n_lines"
        ;;
      boot)
        echo "# $(nps_boot_log "$svc")"
        npl_tail_lines "$(nps_boot_log "$svc")" "$n_lines"
        ;;
    esac
    ;;
  snap)
    npl_snap_service "${1:-accounting}"
    echo ""
    echo "batch_failure_audit (latest):"
    npl_batch_failures | head -5 || true
    ;;
  batch)
    job="${1:?job name required}"
    jt="${2:-}"
    echo "=== batch ${job} ${jt:+(job_time=$jt)} ==="
    npl_batch_status "$job" "$jt" | while IFS='|' read -r eid status start end msg; do
      [[ -n "${eid:-}" ]] || continue
      echo "  exec=$eid status=$status start=$start end=$end"
      [[ -n "${msg:-}" ]] && echo "    exit: ${msg:0:200}"
    done
    echo ""
    echo "--- accounting errors ---"
    npl_grep_errors "$(npl_app_log accounting)" 15 || true
    echo ""
    npl_batch_failures | head -3 || true
    ;;
  *)
    echo "unknown: $cmd" >&2
    usage 1
    ;;
esac
