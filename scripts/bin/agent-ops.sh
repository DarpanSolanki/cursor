#!/usr/bin/env bash
# Autonomous workspace ops — agents call this; do not re-decide manually.
#
#   agent-ops.sh preflight              # session: service status + write ops state
#   agent-ops.sh before-test <apiName>  # smart ensure (compile only if Java changed)
#   agent-ops.sh on-failure [svc] [api] [job_time]
#   agent-ops.sh verify-dpi             # full DPI sanity chain
#   agent-ops.sh write-state
#   agent-ops.sh env-smoke              # db ping per env-matrix → workspace-ops-state.md
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
# shellcheck source=../lib/agent-ops-lib.sh
source "$ROOT/scripts/lib/agent-ops-lib.sh"

cmd="${1:-preflight}"
shift || true

case "$cmd" in
  preflight|state|write-state)
    # The autopilot runs preflight on every user message. Re-probing services and
    # nine env wrappers to rewrite state that is seconds old is pure wall-clock —
    # the state file itself tells sessions to read it instead of re-probing.
    state_file="$ROOT/.cursor/workspace-ops-state.md"
    ttl="${AGENT_OPS_PREFLIGHT_TTL:-600}"
    if [[ "$cmd" == "preflight" && -z "${AGENT_OPS_PREFLIGHT_FORCE:-}" && -f "$state_file" ]]; then
      age=$(( $(date +%s) - $(stat -c %Y "$state_file" 2>/dev/null || echo 0) ))
      if (( age < ttl )); then
        head -20 "$state_file"
        echo ""
        echo "_(cached ${age}s ago; TTL ${ttl}s — AGENT_OPS_PREFLIGHT_FORCE=1 to re-probe)_"
        exit 0
      fi
    fi
    aops_write_state
    # Remote env reachability changes far slower than local service state. process_matrix.json
    # declares env_smoke at 3600s; preflight's own 600s cycle was re-probing 9 remote envs six
    # times more often than that contract asks for, at ~5s a pass.
    if [[ -f "$ROOT/scripts/env/env-matrix.json" ]]; then
      env_ttl="${AGENT_OPS_ENV_SMOKE_TTL:-3600}"
      env_stamp="$ROOT/.cursor/.env-smoke-stamp"
      env_age=$(( $(date +%s) - $(stat -c %Y "$env_stamp" 2>/dev/null || echo 0) ))
      if (( env_age >= env_ttl )) || [[ -n "${AGENT_OPS_PREFLIGHT_FORCE:-}" ]]; then
        bash "$ROOT/scripts/bin/env-smoke.sh" --write-state >/dev/null 2>&1 || true
        touch "$env_stamp"
      fi
    fi
    head -20 "$state_file" 2>/dev/null
    ;;
  env-smoke|--env-smoke)
    bash "$ROOT/scripts/bin/env-smoke.sh" --write-state "$@"
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
