#!/usr/bin/env bash
# afterShellExecution — flag pending KG enrich after successful git commit.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
input=$(cat)
read -r command output <<<"$(python3 -c "
import json,sys
d=json.load(sys.stdin)
print(d.get('command',''))
print(d.get('output','')[:500])
" <<<"$input")"

if [[ ! "$command" =~ git[[:space:]]+commit ]]; then
  echo '{}'
  exit 0
fi

# Heuristic: commit succeeded (no fatal/error in first lines)
if echo "$output" | grep -qiE 'nothing to commit|no changes added|failed|fatal:'; then
  echo '{}'
  exit 0
fi

mkdir -p "$ROOT/.cursor" "$ROOT/scripts/scratch/logs"
date -u +%Y-%m-%dT%H:%M:%SZ >"$ROOT/.cursor/.pending-kg-rebuild"

# Self-heal: always attempt tiered enrich (FULL/CASES/SKIP) — do not wait for push.
# Cursor Hooks must be enabled in Settings for this hook to fire; agents also run
# enrichment-sync via workspace-autopilot end / ship-and-continue.
if [[ -x "$ROOT/scripts/bin/enrichment-sync.sh" ]]; then
  timeout 180 bash "$ROOT/scripts/bin/enrichment-sync.sh" >>"$ROOT/.cursor/enrichment-sync.log" 2>&1 || true
fi

# Drain learning_bus so PASS/gotcha events stay compact for hub/KG cases.
timeout 30 env PYTHONPATH="$ROOT/scripts/testing${PYTHONPATH:+:$PYTHONPATH}" \
  python3 -c "from learning_bus import compact_bus; print(compact_bus())" \
  >>"$ROOT/scripts/scratch/logs/learning-bus-drain.log" 2>&1 || true

echo '{"additional_context":"Git commit completed — enrichment-sync + learning_bus compact attempted (see .cursor/enrichment-sync.log). Enable Cursor Settings → Hooks if this did not run."}'
