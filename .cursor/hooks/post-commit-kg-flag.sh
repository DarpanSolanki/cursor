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

mkdir -p "$ROOT/.cursor"
date -u +%Y-%m-%dT%H:%M:%SZ >"$ROOT/.cursor/.pending-kg-rebuild"

# Auto-sync when watermark drifted (extended sessions / checkout without kg-switch)
if ! python3 "$ROOT/scripts/lib/kg_watermark_gate.py" check --soft >/dev/null 2>&1; then
  timeout 120 bash "$ROOT/scripts/bin/enrichment-sync.sh" >/dev/null 2>&1 || true
fi

echo '{"additional_context":"Git commit completed — when changelog is prepended for a stable fix, run scripts/bin/kg-enrich.sh to fold cases into the KG. If KG was stale, enrichment-sync auto-ran."}'
