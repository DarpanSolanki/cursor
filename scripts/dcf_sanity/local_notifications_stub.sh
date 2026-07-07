#!/usr/bin/env bash
# Local notifications HTTP stub for DCF e2e — answers getMessage/sendEmail on :8015
# so accounting's createSuccessResponse path completes without a live notifications svc.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PORT="${DCF_NOTIFICATIONS_STUB_PORT:-8015}"
STATE_DIR="$ROOT/scripts/scratch/services"
PID_FILE="$STATE_DIR/notifications-stub.pid"
LOG_FILE="$STATE_DIR/notifications-stub.log"
STUB_PY="$ROOT/scripts/dcf_sanity/local_notifications_stub.py"

stub_probe() {
  local code
  code="$(curl -s -m 5 -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:${PORT}/notifications/template/response/mfi/v1/getMessage" 2>/dev/null || echo 000)"
  [[ "$code" == "200" ]]
}

free_port() {
  local pids
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$pids" ]] && return 0
  if [[ -f "$PID_FILE" ]]; then
    local sp
    read -r sp <"$PID_FILE" || true
    if [[ -n "${sp:-}" ]] && stub_probe; then
      return 0
    fi
  fi
  echo "  notifications-stub: freeing :$PORT (pids: $pids)"
  kill -TERM $pids 2>/dev/null || true
  sleep 2
  pids="$(lsof -tiTCP:"$PORT" -sTCP:LISTEN 2>/dev/null || true)"
  [[ -z "$pids" ]] || kill -KILL $pids 2>/dev/null || true
  sleep 1
}

start_stub() {
  mkdir -p "$STATE_DIR"
  free_port
  if stub_probe; then
    echo "  notifications-stub: already up on :$PORT"
    return 0
  fi
  : >"$LOG_FILE"
  nohup python3 "$STUB_PY" >>"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"
  local i
  for i in $(seq 1 20); do
    if stub_probe; then
      echo "  notifications-stub: ready on :$PORT (${i}s)"
      return 0
    fi
    sleep 1
  done
  echo "FAIL: notifications stub not ready on :$PORT" >&2
  tail -20 "$LOG_FILE" >&2 || true
  return 1
}

stop_stub() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    read -r pid <"$PID_FILE" || true
    [[ -n "${pid:-}" ]] && kill -TERM "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
  fi
  free_port
  echo "  notifications-stub: stopped"
}

cmd="${1:-ensure}"
case "$cmd" in
  start|ensure) start_stub ;;
  stop) stop_stub ;;
  probe) stub_probe ;;
  *) echo "usage: $0 {ensure|start|stop|probe}" >&2; exit 1 ;;
esac
