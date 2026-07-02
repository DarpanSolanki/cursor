#!/usr/bin/env bash
# Autonomous workspace ops — agents call this; do not re-decide manually.
#
#   agent-ops.sh preflight              # session: service status + write ops state
#   agent-ops.sh before-test <apiName>  # smart ensure (compile only if Java changed)
#   agent-ops.sh on-failure [svc] [api] [job_time]
#   agent-ops.sh verify-dpi             # full DPI sanity chain
#   agent-ops.sh write-state
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib/agent-ops-lib.sh"

cmd="${1:-preflight}"
shift || true

case "$cmd" in
  preflight|state|write-state)
    aops_write_state
    cat "$ROOT/.cursor/workspace-ops-state.md" 2>/dev/null | head -20
    ;;
  before-test)
    api="${1:?apiName required}"
    svc="${2:-$(aops_service_for_api "$api")}"
    aops_before_test "$api" "$svc"
    ;;
  on-failure)
    aops_on_failure "${1:-accounting}" "${2:-}" "${3:-}"
    ;;
  verify-dpi|dpi-sanity)
    bash "$ROOT/scripts/bin/dpi-sanity.sh"
    ;;
  ensure)
    svc="${1:-accounting}"
    compile_flag=0
    [[ "${2:-}" == "--compile" ]] && compile_flag=1
    aops_run_ensure "$svc" "$compile_flag"
    ;;
  -h|--help)
    sed -n '2,10p' "$0"
    ;;
  *)
    echo "unknown: $cmd" >&2
    exit 1
    ;;
esac
