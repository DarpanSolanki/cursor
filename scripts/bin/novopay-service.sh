#!/usr/bin/env bash
# Local Novopay microservice lifecycle — stop stale processes, compile, bootRun, wait for probe.
#
#   novopay-service.sh status [accounting|actor|task|all]
#   novopay-service.sh stop   <service>
#   novopay-service.sh start  <service> [--compile]
#   novopay-service.sh restart <service> [--compile]
#   novopay-service.sh ensure <service> [--compile]   # restart if probe fails
#   novopay-service.sh wait   <service> [timeout_sec]
#
# Agents: run `ensure accounting --compile` before DPI/batch ntest; never skip sanity because port is down.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/novopay-service-lib.sh"

usage() {
  sed -n '2,12p' "$0"
  exit "${1:-0}"
}

known_services() { echo accounting actor task payments; }

resolve_services() {
  local arg="${1:-all}"
  if [[ "$arg" == "all" ]]; then
    known_services
    return 0
  fi
  nps_service_repo "$arg" >/dev/null 2>&1 || { echo "unknown service: $arg" >&2; usage 1; }
  echo "$arg"
}

want_compile=0
for a in "$@"; do
  [[ "$a" == "--compile" ]] && want_compile=1
done

cmd="${1:-}"
shift || true
[[ "$cmd" == "-h" || "$cmd" == "--help" ]] && usage 0

case "$cmd" in
  status)
    svc_arg="${1:-all}"
    rc=0
    while read -r svc; do
      nps_status_service "$svc" || rc=1
    done < <(resolve_services "$svc_arg")
    exit "$rc"
    ;;
  stop)
    svc="${1:-}"
    [[ -n "$svc" ]] || usage 1
    nps_stop_service "$svc"
    ;;
  start)
    svc="${1:-}"
    [[ -n "$svc" ]] || usage 1
    nps_start_service "$svc" "$want_compile"
    ;;
  restart)
    svc="${1:-}"
    [[ -n "$svc" ]] || usage 1
    echo "=== restart $svc ==="
    nps_stop_service "$svc" || true
    sleep 1
    nps_start_service "$svc" "$want_compile"
    ;;
  ensure)
    svc="${1:-}"
    [[ -n "$svc" ]] || usage 1
    if nps_probe_service "$svc"; then
      echo "  $svc: probe OK — no restart"
      exit 0
    fi
    echo "=== ensure $svc (probe failed — restarting) ==="
    nps_stop_service "$svc" || true
    sleep 1
    nps_start_service "$svc" "$want_compile"
    ;;
  wait)
    svc="${1:-}"
    timeout="${2:-180}"
    [[ -n "$svc" ]] || usage 1
    nps_wait_service "$svc" "$timeout"
    ;;
  "")
    usage 0
    ;;
  *)
    echo "unknown command: $cmd" >&2
    usage 1
    ;;
esac
