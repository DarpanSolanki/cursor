#!/usr/bin/env bash
# Refresh cross-session git workspace state (local only, no fetch — fast).
# Usage:
#   git-workspace-status.sh           # human summary + write .cursor/git-workspace-state.json
#   git-workspace-status.sh --json
#   git-workspace-status.sh --quiet   # write only, no stdout
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ARGS=(status --write)
QUIET=0
for a in "$@"; do
  case "$a" in
    --json) ARGS+=(--json) ;;
    --quiet|-q) QUIET=1 ;;
  esac
done
if [[ "$QUIET" == 1 && " ${ARGS[*]} " != *" --json "* ]]; then
  python3 "$ROOT/scripts/bin/git_workspace.py" "${ARGS[@]}" >/dev/null
else
  python3 "$ROOT/scripts/bin/git_workspace.py" "${ARGS[@]}"
fi
