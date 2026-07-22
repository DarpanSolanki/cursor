#!/usr/bin/env bash
# Smart disk cleanup for sliProd — service archived logs, scratch, pycache, large ops logs.
# Local dev uses gradle bootRun (novopay-service-lib.sh); archived log rotation is safe to purge.
#
# Usage:
#   workspace-disk-clean.sh              audit only (default)
#   workspace-disk-clean.sh --clean      apply safe removals
#   workspace-disk-clean.sh --clean --verbose
#   workspace-disk-clean.sh --audit-json  machine-readable audit
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CLEAN=0
VERBOSE=0
JSON=0
ACTIVE_LOG_MAX="${ACTIVE_LOG_MAX:-10485760}"   # 10MB — truncate inactive-service active logs above this
ARCHIVE_AGE_DAYS="${ARCHIVE_AGE_DAYS:-0}"      # 0 = all archived dirs

for a in "$@"; do
  case "$a" in
    --clean|-c) CLEAN=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    --audit-json) JSON=1 ;;
  esac
done

log() { [[ "$VERBOSE" == 1 || "$JSON" == 0 ]] && echo "$*"; }
vlog() { [[ "$VERBOSE" == 1 ]] && echo "  $*"; }

bytes_before=0
bytes_after=0
actions=()
issues=0

dir_bytes() {
  local d="$1"
  [[ -d "$d" ]] || { echo 0; return; }
  du -sb "$d" 2>/dev/null | awk '{print $1}' || echo 0
}

file_bytes() {
  local f="$1"
  [[ -f "$f" ]] || { echo 0; return; }
  stat -c%s "$f" 2>/dev/null || echo 0
}

service_running() {
  local repo="$1"
  pgrep -f "gradle.*bootRun.*${repo}" >/dev/null 2>&1
}

record_action() {
  actions+=("$1")
}

# --- 1. Service archived / archive log dirs (logback rotation — not read by novopay-logs.sh) ---
archive_bytes=0
while IFS= read -r -d '' d; do
  sz=$(dir_bytes "$d")
  archive_bytes=$((archive_bytes + sz))
  if [[ "$CLEAN" == 1 ]]; then
    rm -rf "$d"
    record_action "removed archived logs: $d ($(( sz / 1048576 ))MB)"
  else
    record_action "archived logs: $d ($(( sz / 1048576 ))MB)"
    issues=$((issues + 1))
  fi
done < <(find "$ROOT" -type d \( -path '*/logs/*/archived' -o -path '*/logs/*/archive' \) \
  ! -path '*/scripts/scratch/*' -print0 2>/dev/null)

# --- 2. Active logs — truncate only when service is DOWN and log > ACTIVE_LOG_MAX ---
for repo_dir in "$ROOT"/trustt-platform-* "$ROOT"/novopay-platform-*; do
  [[ -d "$repo_dir/logs" ]] || continue
  repo=$(basename "$repo_dir")
  running=0
  service_running "$repo" && running=1
  while IFS= read -r -d '' f; do
    [[ "$f" == *"/archived/"* || "$f" == *"/archive/"* ]] && continue
    sz=$(file_bytes "$f")
    [[ "$sz" -le "$ACTIVE_LOG_MAX" ]] && continue
    if [[ "$running" -eq 1 ]]; then
      vlog "skip active log (service up): $f ($(( sz / 1048576 ))MB)"
      continue
    fi
    if [[ "$CLEAN" == 1 ]]; then
      : >"$f"
      record_action "truncated inactive-service log: $f (was $(( sz / 1048576 ))MB)"
    else
      record_action "large inactive log: $f ($(( sz / 1048576 ))MB) — truncate on --clean"
      issues=$((issues + 1))
    fi
  done < <(find "$repo_dir/logs" -type f -name '*.log' -print0 2>/dev/null)
done

# --- 3. Python bytecode under scripts/ ---
pycache_n=$(find scripts -type d -name __pycache__ 2>/dev/null | wc -l)
if [[ "$pycache_n" -gt 0 ]]; then
  if [[ "$CLEAN" == 1 ]]; then
    find scripts -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    record_action "removed scripts __pycache__ ($pycache_n dirs)"
  else
    record_action "scripts __pycache__: $pycache_n dir(s)"
    issues=$((issues + 1))
  fi
fi

# --- 4. Gradle bootRun nohup logs at repo roots (safe truncate) ---
for f in "$ROOT"/trustt-platform-*/nohup.out "$ROOT"/novopay-platform-*/nohup.out; do
  [[ -f "$f" ]] || continue
  sz=$(file_bytes "$f")
  [[ "$sz" -le 65536 ]] && continue
  if [[ "$CLEAN" == 1 ]]; then
    : >"$f"
    record_action "truncated nohup.out: $f"
  else
    record_action "large nohup.out: $f ($(( sz / 1024 ))KB)"
    issues=$((issues + 1))
  fi
done

# --- 5. Delegate scratch + KG cache to workspace-hygiene when cleaning ---
if [[ "$CLEAN" == 1 ]]; then
  bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean --verbose 2>/dev/null || true
fi

if [[ "$JSON" == 1 ]]; then
  python3 - "$CLEAN" "$issues" "$archive_bytes" <<'PY'
import json, sys
clean, issues, archive = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
actions = [l for l in sys.stdin.read().splitlines() if l.strip()]
print(json.dumps({"clean": bool(clean), "issues": issues, "archive_bytes_hint": archive, "actions": actions}, indent=2))
PY
  exit 0
fi

echo "=== workspace disk clean ==="
echo "Mode: $([[ "$CLEAN" == 1 ]] && echo CLEAN || echo AUDIT)"
if [[ ${#actions[@]} -eq 0 ]]; then
  echo "✓ Nothing to clean"
else
  for a in "${actions[@]}"; do
    echo "  · $a"
  done
fi
if [[ "$CLEAN" == 0 && "$issues" -gt 0 ]]; then
  echo "-- $issues reclaimable item(s) — run: bash scripts/bin/workspace-disk-clean.sh --clean"
fi
