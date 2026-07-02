#!/usr/bin/env bash
# afterShellExecution — sync KG when user runs git checkout / git switch in a service repo.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
CMD=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" 2>/dev/null || true)
if [[ ! "$CMD" =~ git[[:space:]]+(checkout|switch) ]]; then
  exit 0
fi
# Only react when checkout is inside workspace novopay-* / trustt-* repos
if [[ ! "$CMD" =~ (novopay-|trustt-) ]]; then
  # still sync — branch may have changed in cwd even without path in command
  :
fi
if [[ -x "$ROOT/scripts/bin/kg-switch.sh" ]]; then
  timeout 600 bash "$ROOT/scripts/bin/kg-switch.sh" --quiet 2>&1 | tail -3 >&2 || true
fi
exit 0
