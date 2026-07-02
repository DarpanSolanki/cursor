#!/usr/bin/env bash
# Shared helpers for scripts/bin/novopay-service.sh
set -euo pipefail

_NPS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
_NPS_STATE="${NPS_STATE_DIR:-$_NPS_ROOT/scripts/scratch/services}"
mkdir -p "$_NPS_STATE"

nps_service_repo() {
  case "$1" in
    accounting) echo "novopay-platform-accounting-v2" ;;
    actor) echo "novopay-platform-actor" ;;
    task) echo "novopay-platform-task" ;;
    *) return 1 ;;
  esac
}

nps_service_port() {
  case "$1" in
    accounting) echo "8002" ;;
    actor) echo "8003" ;;
    task) echo "8019" ;;
    *) return 1 ;;
  esac
}

nps_service_profile() {
  case "$1" in
    accounting|actor|task) echo "mfi" ;;
    *) return 1 ;;
  esac
}

nps_service_probe_url() {
  case "$1" in
    accounting) echo "http://localhost:8002/accounting/api/v1/getLoanAccountBasicDetails" ;;
    actor) echo "http://localhost:8003/actor/api/v1/getUserBasicDetails" ;;
    task) echo "http://localhost:8019/task/api/v1/getTaskList" ;;
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
    task)
      echo '{"headers":{"tenant_code":"mfi","user_id":"53","stan":"nps_probe","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{}}'
      ;;
    *) return 1 ;;
  esac
}

nps_pid_file() { echo "$_NPS_STATE/$1.pid"; }
nps_boot_log() { echo "$_NPS_STATE/$1-bootrun.log"; }

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
  local url body code
  url="$(nps_service_probe_url "$svc")"
  body="$(nps_service_probe_body "$svc")"
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "$url" \
    -H 'Content-Type: application/json' -d "$body" 2>/dev/null || echo 000)"
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
  echo "  $svc: bootRun profile=$profile (log $bl)"
  (
    cd "$dir"
    nohup ./gradlew bootRun --args="--spring.profiles.active=${profile}" >>"$bl" 2>&1 &
    echo $! >"$pf"
  )
  nps_wait_service "$svc" "${NPS_START_TIMEOUT:-180}"
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
