#!/usr/bin/env bash
# Push to origin after ship-loop gate (auto workspace-close if pending).
#
# Usage:
#   push-origin.sh                    # push current branch: git push -u origin HEAD
#   push-origin.sh origin my-branch   # pass through to git push
#   SHIP_PUSH_NO_AUTO_CLOSE=1 push-origin.sh …  # skip auto-close (fail if stale)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PENDING="$ROOT/.cursor/.pending-ship-work.json"
PASSED="$ROOT/.cursor/.ship-loop-passed.json"
GATE="$ROOT/scripts/lib/ship_push_gate.py"

if [[ ! -x "$GATE" ]]; then
  GATE="python3 $ROOT/scripts/lib/ship_push_gate.py"
fi

_run_close_if_needed() {
  if [[ "${SHIP_PUSH_NO_AUTO_CLOSE:-}" == "1" ]]; then
    if python3 "$ROOT/scripts/lib/ship_push_gate.py" --needs-close 2>/dev/null; then
      echo "push-origin: ship loop stale — run: bash scripts/bin/workspace-close.sh --from-pending" >&2
      return 1
    fi
    return 0
  fi
  if ! python3 "$ROOT/scripts/lib/ship_push_gate.py" --needs-close 2>/dev/null; then
    return 0
  fi
  echo "=== push-origin: auto workspace-close (pending ship work) ===" >&2
  local -a close_args=(--from-pending)
  local api
  while IFS= read -r api; do
    [[ -n "$api" ]] && close_args+=(--api "$api")
  done < <(python3 "$ROOT/scripts/lib/ship_push_gate.py" --pending-apis)
  # Merge / sync commits: skip brain CHANGELOG hard-fail during close
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --is-merge-head 2>/dev/null; then
    export SHIP_CLOSE_ALLOW_MERGE=1
  fi
  bash "$ROOT/scripts/bin/workspace-close.sh" "${close_args[@]}"
}

_run_close_if_needed

if [[ $# -eq 0 ]]; then
  set -- -u origin HEAD
fi

# Block upstream — origin only
for arg in "$@"; do
  if [[ "$arg" =~ upstream|khoslalabs ]]; then
    echo "push-origin: blocked — use origin only (darpan boundary)" >&2
    exit 1
  fi
done

exec git push "$@"
