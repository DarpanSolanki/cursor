#!/usr/bin/env bash
# Decision helpers for scripts/bin/agent-ops.sh
set -euo pipefail

_AOPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$_AOPS_ROOT/scripts/lib/novopay-service-lib.sh"

aops_service_for_api() {
  local api="${1,,}"
  case "$api" in
    *actor*|getuser*|getemployee*) echo actor ;;
    *task*) echo task ;;
    *) echo accounting ;;
  esac
}

aops_is_batch_api() {
  local api="$1"
  [[ "$api" =~ [Bb]atch$ ]] || [[ "$api" =~ Job$ ]] || [[ "$api" =~ Calculation$ ]] || [[ "$api" =~ Booking$ ]] || [[ "$api" =~ Billing$ ]]
}

aops_is_dpi_api() {
  local api="${1,,}"
  [[ "$api" == dpi* ]]
}

aops_is_money_test() {
  local api="$1"
  aops_is_batch_api "$api" || aops_is_dpi_api "$api" || [[ "${1,,}" == *disburse* ]] || [[ "${1,,}" == *foreclos* ]]
}

aops_repo_dir() {
  case "$1" in
    accounting) echo "$_AOPS_ROOT/novopay-platform-accounting-v2" ;;
    actor) echo "$_AOPS_ROOT/novopay-platform-actor" ;;
    task) echo "$_AOPS_ROOT/novopay-platform-task" ;;
    *) return 1 ;;
  esac
}

aops_java_newer_than_boot() {
  local svc="$1"
  local repo bl
  repo="$(aops_repo_dir "$svc")" || return 1
  bl="$(nps_boot_log "$svc")"
  [[ -d "$repo/src" ]] || return 1
  [[ -f "$bl" ]] || return 0
  find "$repo/src" -name '*.java' -newer "$bl" -print -quit 2>/dev/null | grep -q .
}

aops_probe_ok() {
  nps_probe_service "$1" 2>/dev/null
}

aops_decide_ensure() {
  local api="$1" svc="${2:-accounting}"
  if aops_is_money_test "$api"; then
    echo yes
    return 0
  fi
  if aops_probe_ok "$svc"; then
    echo skip
  else
    echo yes
  fi
}

aops_decide_compile() {
  local api="$1" svc="${2:-accounting}"
  if [[ "${AOPS_FORCE_COMPILE:-0}" == "1" ]]; then
    echo yes
    return 0
  fi
  if aops_is_batch_api "$api" || aops_is_dpi_api "$api"; then
    if aops_java_newer_than_boot "$svc"; then
      echo yes
      return 0
    fi
  fi
  if aops_java_newer_than_boot "$svc"; then
    echo yes
  else
    echo no
  fi
}

aops_run_ensure() {
  local svc="$1" compile="${2:-0}"
  local flag=()
  [[ "$compile" == "1" ]] && flag=(--compile)
  bash "$_AOPS_ROOT/scripts/bin/novopay-service.sh" ensure "$svc" "${flag[@]}"
}

aops_before_test() {
  local api="$1" svc="${2:-$(aops_service_for_api "$api")}"
  local ensure compile
  ensure="$(aops_decide_ensure "$api" "$svc")"
  [[ "$ensure" == "skip" ]] && return 0
  compile="$(aops_decide_compile "$api" "$svc")"
  [[ "$compile" == "yes" ]] && compile=1 || compile=0
  echo "agent-ops: ensure $svc compile=$compile (api=$api)"
  aops_run_ensure "$svc" "$compile"
}

aops_on_failure() {
  local svc="${1:-accounting}" api="${2:-}" job_time="${3:-}"
  bash "$_AOPS_ROOT/scripts/bin/novopay-logs.sh" snap "$svc" || true
  if [[ -n "$api" ]] && aops_is_batch_api "$api"; then
    bash "$_AOPS_ROOT/scripts/bin/novopay-logs.sh" batch "$api" "$job_time" || true
  fi
}

aops_write_state() {
  local state="$_AOPS_ROOT/.cursor/workspace-ops-state.md"
  local utc svc status accounting_ok
  utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  mkdir -p "$_AOPS_ROOT/.cursor"
  {
    echo "# Workspace ops state (auto-generated — do not edit)"
    echo ""
    echo "Updated: ${utc}"
    echo ""
    echo "## Local services"
    for svc in accounting actor task; do
      if status="$(nps_status_service "$svc" 2>&1)"; then
        echo "- **${svc}**: ${status}"
      else
        echo "- **${svc}**: ${status}"
      fi
    done
    echo ""
    echo "## Autonomous playbook (agents)"
    echo "| Trigger | Auto action |"
    echo "|---------|-------------|"
    echo "| Session start | Read this file + \`workspace-kg-state.md\` |"
    echo "| Before batch/DPI/disburse test | \`agent-ops.sh before-test <api>\` |"
    echo "| After accounting Java edit + test | ensure + compile if .java newer than boot log |"
    echo "| DPI code shipped / user says sanity | \`agent-ops.sh verify-dpi\` |"
    echo "| Wait >10s or HTTP 000 | \`novopay-logs.sh snap accounting\` |"
    echo "| ntest failure | auto snap + batch log if batch API |"
    echo ""
    echo "## Log paths (accounting)"
    echo "- app: \`$(nps_app_log accounting)\`"
    echo "- boot: \`$(nps_boot_log accounting)\`"
    echo ""
    echo "Rule: \`.cursor/rules/autonomous-workspace-ops.mdc\`"
  } >"$state"
}
