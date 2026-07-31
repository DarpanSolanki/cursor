#!/usr/bin/env bash
# Stack preflight for ship/test chain — hygiene before any ntest or ship-loop run.
# Usage: stack-doctor.sh [--remediate] [--json]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REMEDIATE=0
AS_JSON=0
for arg in "$@"; do
  case "$arg" in
    --remediate) REMEDIATE=1 ;;
    --json) AS_JSON=1 ;;
    -h|--help)
      echo "Usage: stack-doctor.sh [--remediate] [--json]"
      exit 0
      ;;
  esac
done

fail=0
reds=()
oks=()
warns=()

note_ok() { oks+=("$1"); }
note_warn() { warns+=("$1"); }
note_fail() { reds+=("$1"); fail=1; }

PGHOST="${YB_HOST:-127.0.0.1}"
PGPORT="${YB_PORT:-5433}"
PGUSER="${YB_USER:-yugabyte}"
PGDATABASE="${YB_DB:-yugabyte}"
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo "=== stack-doctor ==="

# --- Sticky pending GC (clean+pushed zombies) ---
if [[ -f "$ROOT/.cursor/.pending-ship-work.json" ]]; then
  _gc_out="$(python3 "$ROOT/scripts/lib/pending_ship_gc.py" 2>/dev/null || true)"
  if [[ -n "$_gc_out" ]]; then
    note_ok "pending_gc:$_gc_out"
  fi
fi

# --- DB reachable ---
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -A -c "SELECT 1" >/dev/null 2>&1; then
  note_ok "db:${PGHOST}:${PGPORT}"
else
  note_fail "db_unreachable:${PGHOST}:${PGPORT}"
fi

# --- Service health (accounting required; payments only when pending touches payments) ---
_need_payments=0
if [[ -f "$ROOT/.cursor/.pending-ship-work.json" ]]; then
  _need_payments="$(python3 -c "
import json
from pathlib import Path
p=Path('$ROOT/.cursor/.pending-ship-work.json')
d=json.loads(p.read_text()) if p.is_file() else {}
repos=set(d.get('repos') or [])
files=' '.join(d.get('files') or [])
print(1 if 'trustt-platform-payments' in repos or 'novopay-platform-payments' in repos or 'payments/' in files else 0)
" 2>/dev/null || echo 0)"
fi
_svc_list=(accounting)
[[ "$_need_payments" == "1" ]] && _svc_list+=(payments)
for svc in "${_svc_list[@]}"; do
  st="$(bash "$ROOT/scripts/bin/novopay-service.sh" status "$svc" 2>/dev/null | grep -E '^UP |^DOWN ' | head -1 || echo DOWN)"
  if [[ "$st" == UP* ]]; then
    note_ok "health:$svc"
  else
    if [[ "$REMEDIATE" -eq 1 ]]; then
      echo "→ stack-doctor: ensure $svc"
      bash "$ROOT/scripts/bin/novopay-service.sh" ensure "$svc" >/dev/null 2>&1 || true
      bash "$ROOT/scripts/bin/novopay-service.sh" wait "$svc" 60 >/dev/null 2>&1 || true
      st="$(bash "$ROOT/scripts/bin/novopay-service.sh" status "$svc" 2>/dev/null | grep -E '^UP |^DOWN ' | head -1 || echo DOWN)"
      if [[ "$st" == UP* ]]; then
        note_ok "health:$svc (remediated)"
      elif [[ "$svc" == "payments" && "$_need_payments" != "1" ]]; then
        note_warn "health:payments down (not required for this pending scope)"
      else
        note_fail "health:$svc down after ensure"
      fi
    elif [[ "$svc" == "payments" && "$_need_payments" != "1" ]]; then
      note_warn "health:payments down (skipped — not in pending repos)"
    else
      note_fail "health:$svc down"
    fi
  fi
done

# --- Stuck STARTED batch executions (all jobs, not only dpi) ---
if psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -A >/dev/null 2>&1; then
  stuck="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -A <<'SQL' 2>/dev/null || echo 0
SELECT COUNT(*)::text
FROM mfi_batch.batch_job_execution bje
WHERE bje.status IN ('STARTED', 'STARTING', 'UNKNOWN')
  AND bje.create_time < NOW() - INTERVAL '3 minutes';
SQL
)"
  stuck="${stuck//[[:space:]]/}"
  if [[ "${stuck:-0}" == "0" ]]; then
    note_ok "batch:no_stuck_started"
  else
    if [[ "$REMEDIATE" -eq 1 ]]; then
      abandoned="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -A \
        -f "$ROOT/scripts/dpic/sql/helpers/dpi_abandon_stuck_batch_jobs.sql" \
        -v older_than_seconds=180 2>/dev/null | grep -E '^[0-9]+$' | tail -1 || echo 0)"
      abandoned="${abandoned//[[:space:]]/}"
      if [[ "${abandoned:-0}" =~ ^[0-9]+$ && "${abandoned:-0}" -gt 0 ]]; then
        bash "$ROOT/scripts/bin/novopay-service.sh" restart accounting >/dev/null 2>&1 || true
        note_ok "batch:abandoned_${abandoned}_stuck"
      else
        stuck2="$(psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -t -A <<'SQL' 2>/dev/null || echo "$stuck"
SELECT COUNT(*)::text FROM mfi_batch.batch_job_execution bje
WHERE bje.status IN ('STARTED','STARTING','UNKNOWN') AND bje.create_time < NOW() - INTERVAL '3 minutes';
SQL
)"
        stuck2="${stuck2//[[:space:]]/}"
        if [[ "${stuck2:-0}" == "0" ]]; then
          note_ok "batch:stuck_cleared"
        else
          note_warn "batch:stuck_${stuck2}_remain"
        fi
      fi
    else
      note_fail "batch:stuck_started=${stuck}"
    fi
  fi
fi

# --- Stale locks: only fail/clear when flock is free (or holder pid dead).
# Never rm /tmp/flowtest_e2e.lock solely because the file exists — live harness may hold flock.
_lock_flock_held() {
  local lock="$1"
  python3 - "$lock" <<'PY' 2>/dev/null
import fcntl, os, sys
path = sys.argv[1]
if not os.path.exists(path):
    raise SystemExit(1)
fd = os.open(path, os.O_RDWR)
try:
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)  # held
    fcntl.flock(fd, fcntl.LOCK_UN)
    raise SystemExit(1)  # free
finally:
    os.close(fd)
PY
}
_lock_owner_pid_live() {
  local lock="$1"
  local pid
  pid="$(awk -F= '/^pid=/{print $2; exit}' "$lock" 2>/dev/null || true)"
  [[ -n "${pid:-}" && "$pid" =~ ^[0-9]+$ ]] || return 1
  kill -0 "$pid" 2>/dev/null
}
for lock in /tmp/flowtest_e2e.lock /tmp/disburse_loan_sanity.lock /tmp/dcf_e2e.lock "$ROOT/.cursor/.ship-push.lock"; do
  if [[ -f "$lock" ]]; then
    if _lock_flock_held "$lock"; then
      if _lock_owner_pid_live "$lock"; then
        note_fail "lock:held_live:$(basename "$lock")"
      else
        # flock held but pid metadata dead/missing — warn; do not rm under live flock
        note_warn "lock:held_orphan_meta:$(basename "$lock")"
      fi
    else
      # file present, flock free → stale metadata; safe to clear
      if [[ "$REMEDIATE" -eq 1 ]]; then
        rm -f "$lock" 2>/dev/null || true
        note_ok "lock:cleared_stale:$(basename "$lock")"
      else
        note_warn "lock:stale_file:$(basename "$lock") (flock free)"
      fi
    fi
  fi
done
[[ ${#oks[@]} -eq 0 && ${#reds[@]} -eq 0 && ${#warns[@]} -eq 0 ]] && note_ok "locks:clean"

# --- Ship push lock quiesce ---
if [[ -f "$ROOT/.cursor/.ship-push.lock" && "$REMEDIATE" -eq 1 ]]; then
  rm -f "$ROOT/.cursor/.ship-push.lock" 2>/dev/null || true
fi

if [[ "$AS_JSON" -eq 1 ]]; then
  python3 - <<PY
import json
print(json.dumps({
  "ok": ${fail} == 0,
  "reds": $(printf '%s\n' "${reds[@]:-}" | python3 -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))'),
  "warns": $(printf '%s\n' "${warns[@]:-}" | python3 -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))'),
  "oks": $(printf '%s\n' "${oks[@]:-}" | python3 -c 'import json,sys; print(json.dumps([l for l in sys.stdin.read().splitlines() if l]))'),
}, indent=2))
PY
else
  printf 'OK: %s\n' "${oks[@]:-none}"
  [[ ${#warns[@]} -gt 0 ]] && printf 'WARN: %s\n' "${warns[@]}"
  [[ ${#reds[@]} -gt 0 ]] && printf 'FAIL: %s\n' "${reds[@]}"
fi

if [[ "$fail" -ne 0 ]]; then
  echo "stack-doctor: FAIL — run with --remediate for safe auto-fix or fix state manually" >&2
  exit 1
fi
echo "=== stack-doctor: PASS ==="
exit 0
