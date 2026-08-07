#!/usr/bin/env bash
# What is running right now — agents, batch jobs, builds, tests, and the DB they share.
#
# An agent session is opaque from the outside: work that takes minutes looks identical to work
# that has hung, and the honest answer to "is anything happening?" should not require asking.
#
#   scripts/bin/work-monitor.sh          one snapshot
#   scripts/bin/work-monitor.sh --watch  refresh every 3s until Ctrl-C
#
# Read-only. Runs no job, writes no file, touches no database.
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASKS="${CLAUDE_TASK_DIR:-}"
[[ -z "$TASKS" ]] && TASKS="$(ls -td /tmp/claude-*/*/*/tasks 2>/dev/null | head -1)"

blue() { printf '\033[1;36m%s\033[0m\n' "$*"; }
dim()  { printf '\033[2m%s\033[0m\n' "$*"; }

snapshot() {
  printf '\033[1m== workspace activity  %s ==\033[0m\n' "$(date '+%H:%M:%S')"

  blue "-- subagents / background tasks"
  if [[ -n "$TASKS" && -d "$TASKS" ]]; then
    local found=0
    while IFS= read -r f; do
      [[ -z "$f" ]] && continue
      local age size name
      age=$(( $(date +%s) - $(stat -c %Y "$f" 2>/dev/null || echo 0) ))
      size=$(stat -c %s "$f" 2>/dev/null || echo 0)
      name=$(basename "$f" .output)
      if (( age < 90 )); then
        printf '   RUNNING  %-20s %6s bytes  last wrote %ss ago\n' "$name" "$size" "$age"
        found=1
      fi
    done < <(ls -t "$TASKS"/*.output 2>/dev/null | head -12)
    (( found == 0 )) && dim "   none active (no task output written in the last 90s)"
  else
    dim "   no task directory found"
  fi

  blue "-- batch jobs executing in accounting"
  local running
  running=$(PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h localhost -p 5433 -U yugabyte -d yugabyte \
    -t -A -F'|' -c "select job_name||' '||status||' started '||to_char(start_time,'HH24:MI:SS')
      from mfi_batch.batch_job_execution e
      join mfi_batch.batch_job_instance i on i.job_instance_id = e.job_instance_id
      where e.status = 'STARTED' order by e.start_time desc limit 8" 2>/dev/null)
  if [[ -n "$running" ]]; then
    echo "$running" | sed 's/^/   /'
  else
    dim "   none STARTED right now"
  fi

  blue "-- last 5 batch executions"
  PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h localhost -p 5433 -U yugabyte -d yugabyte \
    -t -A -F'|' -c "select to_char(e.start_time,'HH24:MI:SS')||'  '||rpad(i.job_name,34)||' '||e.status
      from mfi_batch.batch_job_execution e
      join mfi_batch.batch_job_instance i on i.job_instance_id = e.job_instance_id
      order by e.start_time desc limit 5" 2>/dev/null | sed 's/^/   /' \
    || dim "   database not reachable"

  blue "-- local processes"
  local procs
  procs=$(pgrep -af 'ntest|gradlew|kg/bin/build|platform_api_map|platform_surface|job_footprint|autonomous-zone' 2>/dev/null \
          | grep -v 'work-monitor' | head -6)
  if [[ -n "$procs" ]]; then
    echo "$procs" | awk '{ $1=""; print "  " substr($0,2,110) }'
  else
    dim "   no harness process running"
  fi

  blue "-- services"
  for p in 8002:accounting 8013:los 8018:simulator 5433:yugabyte 9092:kafka; do
    port="${p%%:*}"; name="${p##*:}"
    if ss -ltn 2>/dev/null | grep -q ":${port} "; then
      printf '   up    %s (%s)\n' "$name" "$port"
    else
      printf '   DOWN  %s (%s)\n' "$name" "$port"
    fi
  done
}

if [[ "${1:-}" == "--watch" ]]; then
  trap 'printf "\n"; exit 0' INT
  while true; do clear; snapshot; dim ""; dim "refreshing every 3s — Ctrl-C to stop"; sleep 3; done
else
  snapshot
fi
