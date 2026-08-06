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

aops_is_bank_leg_disburse_api() {
  local api="${1,,}"
  [[ "$api" == *disburse* ]] || return 1
  case "$api" in
    updateloanaccountpredisbursementdetails) return 1 ;;
  esac
  return 0
}

aops_is_money_test() {
  local api="$1"
  aops_is_batch_api "$api" || aops_is_dpi_api "$api" || aops_is_bank_leg_disburse_api "$api" || [[ "${1,,}" == *foreclos* ]]
}

aops_repo_dir() {
  case "$1" in
    accounting) echo "$_AOPS_ROOT/trustt-platform-accounting" ;;
    actor) echo "$_AOPS_ROOT/trustt-platform-actor" ;;
    task) echo "$_AOPS_ROOT/trustt-platform-task" ;;
    los) echo "$_AOPS_ROOT/trustt-platform-los" ;;
    simulators) echo "$_AOPS_ROOT/trustt-platform-simulators/chameleon" ;;
    *) return 1 ;;
  esac
}

aops_svc_port() {
  case "$1" in
    accounting) echo 8002 ;; actor) echo 8003 ;; los) echo 8013 ;;
    task) echo 8019 ;; simulators) echo 8018 ;; *) echo "" ;;
  esac
}

# Reference point for "is the build stale?".
#
# The boot LOG is the wrong reference: the running service appends to it, so its
# mtime is always ~now and `find -newer` can never match. That silently let a JVM
# started 15:52 serve money-path tests against classes compiled 16:02 on
# 2026-08-03. The process start time (/proc/<pid> mtime) is the only sound anchor;
# fall back to the boot log only when the service is not running.
aops_runtime_ref() {
  local svc="$1" port pid bl
  port="$(aops_svc_port "$svc")"
  if [[ -n "$port" ]]; then
    pid="$(ss -ltnp 2>/dev/null | grep ":${port} " | grep -oP 'pid=\K[0-9]+' | head -1)"
    if [[ -n "$pid" && -d "/proc/$pid" ]]; then
      echo "/proc/$pid"
      return 0
    fi
  fi
  bl="$(nps_boot_log "$svc")"
  [[ -f "$bl" ]] && echo "$bl"
}

aops_java_newer_than_boot() {
  local svc="$1"
  local repo ref
  repo="$(aops_repo_dir "$svc")" || return 1
  [[ -d "$repo/src" ]] || return 1
  ref="$(aops_runtime_ref "$svc")"
  [[ -n "$ref" ]] || return 0
  # Source newer than the running JVM, or compiled classes newer than it (someone
  # built without restarting) both mean the runtime is not what is on disk.
  find "$repo/src" -name '*.java' -newer "$ref" -print -quit 2>/dev/null | grep -q . && return 0
  find "$repo/build/classes/java/main" -name '*.class' -newer "$ref" -print -quit 2>/dev/null | grep -q .
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

aops_prep_dpi_harness() {
  local fixture="$_AOPS_ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"
  [[ -f "$fixture" ]] || return 0
  # shellcheck disable=SC1091
  source "$fixture"
  dpi_prep_before_batch
}

aops_before_test() {
  local api="$1" svc="${2:-$(aops_service_for_api "$api")}"
  local ensure compile
  if aops_is_dpi_api "$api" || aops_is_batch_api "$api"; then
    compile="$(aops_decide_compile "$api" "$svc")"
    [[ "$compile" == "yes" ]] && compile=1 || compile=0
    echo "agent-ops: dpi prep (abandon hung batches + ensure $svc) api=$api"
    export COMPILE="$compile"
    aops_prep_dpi_harness
    return 0
  fi
  ensure="$(aops_decide_ensure "$api" "$svc")"
  [[ "$ensure" == "skip" ]] && return 0
  compile="$(aops_decide_compile "$api" "$svc")"
  [[ "$compile" == "yes" ]] && compile=1 || compile=0
  echo "agent-ops: ensure $svc compile=$compile (api=$api)"
  aops_run_ensure "$svc" "$compile"
  bash "$_AOPS_ROOT/scripts/bin/assert-build-current.sh" "$svc" || {
    echo "agent-ops: STALE RUNTIME on $svc — evidence from it is not verified against HEAD" >&2
    return 1
  }

  # Disburse needs actor + masterdata + bank simulator on every entry path. LOS and Kafka are
  # required only when the run enters through the Kafka producer (TDPQA-54); a direct HTTP
  # disburseLoan call never touches them, so declaring DISBURSE_ENTRY=http skips those two.
  if aops_is_bank_leg_disburse_api "$api"; then
    local los_compile=0 sim_compile=0 actor_compile=0
    local entry="${DISBURSE_ENTRY:-kafka}"
    if [[ "$entry" == "kafka" ]]; then
      if aops_java_newer_than_boot los 2>/dev/null; then los_compile=1; fi
      echo "agent-ops: ensure los compile=$los_compile (kafka producer path)"
      aops_run_ensure los "$los_compile" || {
        echo "FAIL: LOS required for Kafka-path disburse (novopay-service ensure los)." >&2
        echo "      Direct HTTP disburseLoan does not use LOS — set DISBURSE_ENTRY=http." >&2
        return 1
      }
    else
      echo "agent-ops: skip los + kafka readiness (DISBURSE_ENTRY=$entry, direct HTTP disburseLoan)"
    fi
    if aops_java_newer_than_boot actor 2>/dev/null; then actor_compile=1; fi
    echo "agent-ops: ensure actor compile=$actor_compile (getCustomerDetails during disburse)"
    aops_run_ensure actor "$actor_compile" || {
      echo "FAIL: actor required for disburseLoan (getCustomerDetails)" >&2
      return 1
    }
    echo "agent-ops: ensure masterdata (getBulkUniqueMasterData via actor)"
    aops_run_ensure masterdata 0 || {
      echo "FAIL: masterdata required at :8014 for actor getCustomerDetails" >&2
      return 1
    }
    echo "agent-ops: ensure simulators (GST SOAP :8018)"
    aops_run_ensure simulators 0 || {
      echo "FAIL: bank simulator required at :8018" >&2
      return 1
    }
    if [[ "$entry" == "kafka" ]]; then
      nps_assert_disburse_kafka_ready "${NPS_KAFKA_CONSUMER_WAIT:-120}" || return 1
    fi
  fi
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
    # Independent health probes; serial cost is 5 x per-service timeout.
    _svc_tmp="$(mktemp -d)"
    for svc in accounting actor task los simulators; do
      { nps_status_service "$svc" > "$_svc_tmp/$svc" 2>&1 || true; } &
    done
    wait
    for svc in accounting actor task los simulators; do
      echo "- **${svc}**: $(cat "$_svc_tmp/$svc" 2>/dev/null)"
    done
    rm -rf "$_svc_tmp"
    echo ""
    echo "## Disburse Kafka (TDPQA-54)"
    # Group assignment costs a JVM start (~6s). Never ask a broker we just saw DOWN.
    if nps_kafka_tcp_ok; then
      echo "- **Kafka :9092**: UP"
      echo "- topic: \`${nps_disburse_topic}\` · group: \`${nps_disburse_group}\`"
      if nps_kafka_consumer_assigned; then
        echo "- consumer assigned: YES"
      else
        echo "- consumer assigned: NO (accounting LmsMessageBrokerConsumer)"
      fi
    else
      echo "- **Kafka :9092**: DOWN"
      echo "- topic: \`${nps_disburse_topic}\` · group: \`${nps_disburse_group}\`"
      echo "- consumer assigned: UNKNOWN (broker down — not probed)"
    fi
    echo ""
    echo "## Autonomous playbook (agents)"
    echo "| Trigger | Auto action |"
    echo "|---------|-------------|"
    echo "| Session start | Read this file + \`workspace-kg-state.md\` |"
    echo "| Before batch/DPI/disburse test | \`agent-ops.sh before-test <api>\` |"
    echo "| Before Kafka-path disburse | ensure accounting + los + simulators; fail if Kafka consumer not assigned |"
    echo "| After accounting Java edit + test | ensure + compile if .java newer than boot log |"
    echo "| DPI code shipped / user says sanity | \`agent-ops.sh verify-dpi\` |"
    echo "| Wait >10s or HTTP 000 | \`novopay-logs.sh snap accounting\` |"
    echo "| ntest failure | auto snap + batch log if batch API |"
    echo ""
    echo "## Log paths (accounting)"
    # nps_app_log can return non-zero for unknown svc; never leave empty under set -e
    _app_log="$(nps_app_log accounting 2>/dev/null || echo "$_AOPS_ROOT/trustt-platform-accounting/logs/mfi/accounting-mfi.log")"
    _boot_log="$(nps_boot_log accounting 2>/dev/null || echo "$_AOPS_ROOT/scripts/scratch/services/accounting-bootrun.log")"
    echo "- app: \`${_app_log}\`"
    echo "- boot: \`${_boot_log}\`"
    _los_boot="$(nps_boot_log los 2>/dev/null || echo "$_AOPS_ROOT/scripts/scratch/services/los-bootrun.log")"
    echo "- los boot: \`${_los_boot}\`"
    echo ""
    echo "Rule: \`.cursor/rules/00-workspace-core.md\`"
  } >"$state"
}
