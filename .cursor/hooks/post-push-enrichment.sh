#!/usr/bin/env bash
# afterShellExecution — sync KG after successful origin push; refresh session state.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
input=$(cat)
command=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" <<<"$input")

if [[ ! "$command" =~ git[[:space:]]+push ]]; then
  echo '{}'
  exit 0
fi
if [[ "$command" =~ upstream|khoslalabs|trusttai ]]; then
  echo '{}'
  exit 0
fi

# Non-blocking: rebuild if changelog ahead of kg.db (timeout 3 min)
if [[ -x "$ROOT/scripts/bin/enrichment-sync.sh" ]]; then
  timeout 180 bash "$ROOT/scripts/bin/enrichment-sync.sh" >/dev/null 2>&1 || true
fi

python3 - <<'PY'
import json
print(json.dumps({
    "additional_context": "Push completed — enrichment-sync ran (changelog→KG if needed). Verify: `python3 cursor-bundle/kg/bin/kg.py cases <apiName>`."
}))
PY
