#!/usr/bin/env bash
# Push to origin after ship-loop gate (auto workspace-close if pending).
#
# Train-branch sync-first (mfi_integration_vX.Y.Z): before calling this script,
# fetch origin+upstream, base local branch on upstream/<train> tip, replay any
# unique origin commits, then push. Never push from an origin tip that is behind
# upstream without saying STALE and syncing first. See:
#   cursor-bundle/memory/feedback_train_branch_sync_origin_upstream.md
#   .cursor/rules/10-quality-gates.mdc
#
# Usage:
#   push-origin.sh                    # push current branch: git push -u origin HEAD
#   push-origin.sh origin my-branch   # pass through to git push
#   SHIP_PUSH_NO_AUTO_CLOSE=1 push-origin.sh …  # skip auto-close (fail if stale)
#
# Raw `git push` is human emergency-only (break-glass). Agents must use this gate.
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
  # Knowledge-only HEAD skip only when pending also has no service/money code paths.
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --skip-auto-close-knowledge 2>/dev/null; then
    echo "=== push-origin: HEAD+pending knowledge-only — skip auto workspace-close ===" >&2
    return 0
  fi
  if python3 "$ROOT/scripts/lib/ship_push_gate.py" --is-knowledge-head 2>/dev/null; then
    echo "=== push-origin: HEAD is knowledge-only but pending has service/money — auto-close required ===" >&2
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

if ! python3 "$ROOT/scripts/lib/ship_push_gate.py" --satisfied 2>/dev/null; then
  echo "push-origin: BLOCKED — ship loop gate not satisfied for current HEAD." >&2
  echo "Run: bash scripts/bin/workspace-close.sh --from-pending" >&2
  exit 1
fi

if [[ $# -eq 0 ]]; then
  set -- -u origin HEAD
fi

# Block upstream — origin only
for arg in "$@"; do
  if [[ "$arg" =~ upstream|khoslalabs|trusttai ]]; then
    echo "push-origin: blocked — use origin only (darpan boundary)" >&2
    exit 1
  fi
done

exec git push "$@"
