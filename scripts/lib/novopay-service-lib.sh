#!/usr/bin/env bash
# Shared helpers for scripts/bin/novopay-service.sh
set -euo pipefail

_NPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_NPS_STATE="${NPS_STATE_DIR:-$_NPS_ROOT/scripts/scratch/services}"
mkdir -p "$_NPS_STATE"

nps_service_repo() {
  case "$1" in
    accounting) echo "trustt-platform-accounting" ;;
    actor) echo "trustt-platform-actor" ;;
    authorization) echo "trustt-platform-authorization" ;;
    notifications) echo "trustt-platform-notifications" ;;
    task) echo "trustt-platform-task" ;;
    los) echo "trustt-platform-los" ;;
    simulators) echo "trustt-platform-simulators/chameleon" ;;
    masterdata) echo "trustt-platform-masterdata-management" ;;
    *) return 1 ;;
  esac
}

nps_service_port() {
  case "$1" in
    accounting) echo "8002" ;;
    actor) echo "8003" ;;
    authorization) echo "8007" ;;
    notifications) echo "8015" ;;
    task) echo "8019" ;;
    los) echo "8013" ;;
    simulators) echo "8018" ;;
    masterdata) echo "8014" ;;
    *) return 1 ;;
  esac
}

nps_service_profile() {
  case "$1" in
    accounting|actor|authorization|notifications|task|los|masterdata) echo "mfi" ;;
    simulators) echo "" ;;
    *) return 1 ;;
  esac
}

nps_service_probe_url() {
  case "$1" in
    accounting) echo "http://localhost:8002/accounting/api/v1/getLoanAccountBasicDetails" ;;
    actor) echo "http://localhost:8003/actor/api/v1/getUserBasicDetails" ;;
    authorization) echo "http://localhost:8007/authorization/api/v1/getPermissionList" ;;
    notifications) echo "http://localhost:8015/notifications/api/v1/getNotificationsCount" ;;
    task) echo "http://localhost:8019/task/api/v1/getTaskList" ;;
    los) echo "http://localhost:8013/los/api/v1/getOriginateLoanCount" ;;
    simulators) echo "http://localhost:8018/" ;;
    masterdata) echo "http://localhost:8014/masterdata/api/v1/getBulkUniqueMasterData" ;;
    *) return 1 ;;
  esac
}

nps_service_probe_body() {
  case "$1" in
    accounting)
      echo '{"headers":{"tenant_code":"mfi","user_id":"3","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"account_number":"6004041325"}}'
      ;;
    actor)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"user_id":"53"}}'
      ;;
    authorization)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"USER","function_sub_code":"DEFAULT","run_mode":"REAL","transmission_datetime":"'"$(date +%s%3N)"'"},"request":{"user_id":"53"}}'
      ;;
    notifications)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"UNSEEN","run_mode":"REAL","transmission_datetime":"'"$(date +%s%3N)"'"},"request":{}}'
      ;;
    task)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{}}'
      ;;
    los)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL","transmission_datetime":"'"$(date +%s%3N)"'"},"request":{}}'
      ;;
    simulators)
      echo ''
      ;;
    masterdata)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL","transmission_datetime":"'"$(date +%s%3N)"'"},"request":{"data_type_unique_codes":["GENDER"]}}'
      ;;
    *) return 1 ;;
  esac
}

nps_pid_file() { echo "$_NPS_STATE/$1.pid"; }
nps_boot_log() { echo "$_NPS_STATE/$1-bootrun.log"; }
# App runtime log (same paths as npl_app_log) — used by agent-ops state writer
nps_app_log() {
  case "$1" in
    accounting) echo "$_NPS_ROOT/trustt-platform-accounting/logs/mfi/accounting-mfi.log" ;;
    actor) echo "$_NPS_ROOT/trustt-platform-actor/logs/mfi/actor-mfi.log" ;;
    task) echo "$_NPS_ROOT/trustt-platform-task/logs/mfi/task-mfi.log" ;;
    los) echo "$_NPS_ROOT/trustt-platform-los/logs/mfi/los-mfi.log" ;;
    simulators) echo "$_NPS_ROOT/scripts/scratch/services/simulators-bootrun.log" ;;
    masterdata) echo "$_NPS_ROOT/trustt-platform-masterdata-management/logs/mfi/masterdata-mfi.log" ;;
    *) return 1 ;;
  esac
}

nps_pids_on_port() {
  local port="$1"
  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
    return 0
  fi
  if command -v fuser >/dev/null 2>&1; then
    fuser -n tcp "$port" 2>/dev/null | tr -s ' ' '\n' | grep -E '^[0-9]+$' || true
    return 0
  fi
  ss -tlnp 2>/dev/null | awk -v p=":$port" '$4 ~ p {gsub(/.*pid=/, "", $6); gsub(/,.*/, "", $6); if ($6 ~ /^[0-9]+$/) print $6}'
}

nps_gradle_boot_pids() {
  local repo="$1"
  pgrep -f "${repo}.*bootRun" 2>/dev/null || true
  pgrep -f "gradle.*bootRun.*${repo}" 2>/dev/null || true
}

nps_kill_pids() {
  local sig="$1"
  shift
  local pid
  for pid in "$@"; do
    [[ -n "$pid" && "$pid" =~ ^[0-9]+$ ]] || continue
    kill "-$sig" "$pid" 2>/dev/null || true
  done
}

nps_collect_pids() {
  local svc="$1"
  local repo port pf
  repo="$(nps_service_repo "$svc")"
  port="$(nps_service_port "$svc")"
  pf="$(nps_pid_file "$svc")"
  local -a all=()
  if [[ -f "$pf" ]]; then
    read -r gp <"$pf" || true
    [[ -n "${gp:-}" ]] && all+=("$gp")
  fi
  while IFS= read -r p; do [[ -n "$p" ]] && all+=("$p"); done < <(nps_pids_on_port "$port")
  while IFS= read -r p; do [[ -n "$p" ]] && all+=("$p"); done < <(nps_gradle_boot_pids "$repo")
  printf '%s\n' "${all[@]}" | sort -u
}

nps_stop_service() {
  local svc="$1"
  local port pids pid waited=0
  port="$(nps_service_port "$svc")"
  pids="$(nps_collect_pids "$svc" | tr '\n' ' ')"
  if [[ -z "${pids// }" ]]; then
    echo "  $svc: no process on :$port"
    rm -f "$(nps_pid_file "$svc")"
    return 0
  fi
  echo "  $svc: stopping PIDs $pids (port $port)"
  nps_kill_pids TERM $pids
  while [[ "$waited" -lt 20 ]]; do
    [[ -z "$(nps_pids_on_port "$port")" ]] && break
    sleep 1
    waited=$((waited + 1))
  done
  pids="$(nps_collect_pids "$svc" | tr '\n' ' ')"
  if [[ -n "${pids// }" ]]; then
    echo "  $svc: force kill $pids"
    nps_kill_pids KILL $pids
    sleep 1
  fi
  rm -f "$(nps_pid_file "$svc")"
  if [[ -n "$(nps_pids_on_port "$port")" ]]; then
    echo "FAIL: port $port still in use" >&2
    return 1
  fi
  echo "  $svc: stopped"
}

nps_probe_service() {
  local svc="$1"
  local url body code port
  # Simulators: TCP listen is enough (GST SOAP root may not be POST-JSON).
  if [[ "$svc" == "simulators" ]]; then
    port="$(nps_service_port "$svc")"
    if command -v ss >/dev/null 2>&1; then
      ss -tln | grep -qE ":${port}\\b"
      return $?
    fi
    (echo >/dev/tcp/127.0.0.1/"$port") >/dev/null 2>&1
    return $?
  fi
  url="$(nps_service_probe_url "$svc")"
  body="$(nps_service_probe_body "$svc")"
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "$url" \
    -H 'Content-Type: application/json' -d "$body" 2>/dev/null || echo 000)"
  # LOS gateway often returns 4xx for empty probe bodies once the servlet is up.
  # Masterdata same posture for thin probe bodies.
  if [[ "$svc" == "los" || "$svc" == "masterdata" ]]; then
    [[ "$code" =~ ^(200|4[0-9][0-9])$ ]]
    return $?
  fi
  [[ "$code" == "200" ]]
}

nps_wait_service() {
  local svc="$1" timeout="${2:-180}" interval="${3:-2}"
  local elapsed=0 code
  echo "  $svc: waiting up to ${timeout}s for API probe..."
  while [[ "$elapsed" -lt "$timeout" ]]; do
    if nps_probe_service "$svc"; then
      echo "  $svc: ready (${elapsed}s)"
      return 0
    fi
    sleep "$interval"
    elapsed=$((elapsed + interval))
  done
  echo "FAIL: $svc not ready after ${timeout}s" >&2
  local bl
  bl="$(nps_boot_log "$svc")"
  if [[ -f "$bl" ]]; then
    echo "--- tail $bl ---" >&2
    tail -40 "$bl" >&2 || true
  fi
  return 1
}

nps_start_service() {
  local svc="$1" compile="${2:-0}"
  local repo dir profile port pf bl
  repo="$(nps_service_repo "$svc")"
  dir="$_NPS_ROOT/$repo"
  profile="$(nps_service_profile "$svc")"
  port="$(nps_service_port "$svc")"
  pf="$(nps_pid_file "$svc")"
  bl="$(nps_boot_log "$svc")"

  if nps_probe_service "$svc"; then
    echo "  $svc: already up on :$port"
    return 0
  fi

  if [[ -n "$(nps_pids_on_port "$port")" ]]; then
    echo "  $svc: port $port busy — stop first" >&2
    return 1
  fi

  [[ -d "$dir" ]] || { echo "FAIL: missing $dir" >&2; return 1; }
  [[ -x "$dir/gradlew" ]] || { echo "FAIL: no gradlew in $dir" >&2; return 1; }

  if [[ "$compile" == "1" ]]; then
    echo "  $svc: compileJava..."
    (cd "$dir" && ./gradlew compileJava -x test)
  fi

  : >"$bl"
  echo "  $svc: bootRun profile=${profile:-default} (log $bl)"
  (
    cd "$dir"
    if [[ "$svc" == "accounting" || "$svc" == "los" ]]; then
      export MESSAGE_BROKER_XML_PATH="$dir/deploy/application/messagebroker"
      export SPRING_APPLICATION_JSON='{"message.broker.bootstrap.servers":"127.0.0.1:9092"}'
    fi
    if [[ -n "$profile" ]]; then
      nohup ./gradlew bootRun --args="--spring.profiles.active=${profile}" >>"$bl" 2>&1 &
    else
      nohup ./gradlew bootRun >>"$bl" 2>&1 &
    fi
    echo $! >"$pf"
  )
  nps_wait_service "$svc" "${NPS_START_TIMEOUT:-180}"
}

# Fail-closed Kafka readiness for disburseLoan consumer path (TDPQA-54).
nps_kafka_bootstrap="${NPS_KAFKA_BOOTSTRAP:-127.0.0.1:9092}"
nps_disburse_topic="${NPS_DISBURSE_TOPIC:-disburse_loan_api_mfi_local}"
nps_disburse_group="${NPS_DISBURSE_GROUP:-disburse_loan_api_consumer_mfi_local}"

nps_kafka_tcp_ok() {
  (echo >/dev/tcp/127.0.0.1/9092) >/dev/null 2>&1
}

nps_kafka_consumer_assigned() {
  local kg="${KAFKA_HOME:-/home/darpan/Documents/kafka_2.12-3.7.0}/bin/kafka-consumer-groups.sh"
  [[ -x "$kg" ]] || return 1
  "$kg" --bootstrap-server "$nps_kafka_bootstrap" --describe --group "$nps_disburse_group" 2>/dev/null \
    | awk 'NR>1 && $1!="" && $6!="-" {found=1} END{exit found?0:1}'
}

nps_assert_disburse_kafka_ready() {
  local timeout="${1:-90}" elapsed=0
  if ! nps_kafka_tcp_ok; then
    echo "FAIL: Kafka not listening on 127.0.0.1:9092 (required for Kafka-path disburse)" >&2
    return 1
  fi
  echo "  kafka: waiting up to ${timeout}s for consumer group $nps_disburse_group on $nps_disburse_topic..."
  while [[ "$elapsed" -lt "$timeout" ]]; do
    if nps_kafka_consumer_assigned; then
      echo "  kafka: consumer assigned (${elapsed}s)"
      return 0
    fi
    sleep 3
    elapsed=$((elapsed + 3))
  done
  echo "FAIL: no active members in consumer group $nps_disburse_group (accounting LmsMessageBrokerConsumer not ready)" >&2
  return 1
}

nps_status_service() {
  local svc="$1" port pids
  port="$(nps_service_port "$svc")"
  pids="$(nps_collect_pids "$svc" | tr '\n' ' ')"
  if nps_probe_service "$svc"; then
    echo "UP   $svc :$port probe=200 pids=${pids:-none}"
    return 0
  fi
  if [[ -n "${pids// }" ]]; then
    echo "DOWN $svc :$port (processes: $pids, API not 200)"
    return 1
  fi
  echo "DOWN $svc :$port (no listener)"
  return 1
}
