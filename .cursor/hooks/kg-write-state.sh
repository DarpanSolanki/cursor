#!/usr/bin/env bash
# Write .cursor/workspace-kg-state.md from current kg.db (no rebuild / no kg-switch).
# Preserves ## Telemetry (last 20) block appended by kg_state_banner / sync scripts.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
KG="python3 cursor-bundle/kg/bin/kg.py"
STATE=".cursor/workspace-kg-state.md"
PENDING=".cursor/.pending-kg-rebuild"
mkdir -p .cursor

# Preserve existing telemetry before rewrite
TELEMETRY=""
if [[ -f "$STATE" ]]; then
  TELEMETRY="$(PYTHONPATH="$ROOT/scripts/lib" python3 - <<'PY'
from pathlib import Path
from kg_state_banner import TELEMETRY_MARK, _read_telemetry_lines
p = Path(".cursor/workspace-kg-state.md")
if not p.is_file():
    raise SystemExit(0)
text = p.read_text(encoding="utf-8")
lines = _read_telemetry_lines(text)
if lines:
    print(TELEMETRY_MARK)
    print()
    print("\n".join(lines))
PY
)" || true
fi

FRESH=$($KG fresh --no-drift-check 2>&1 || echo "KG fresh check failed")
WM=$($KG watermark --no-drift-check 2>&1 | head -25 || echo "KG watermark failed")
PENDING_NOTE=""
if [[ -f "$PENDING" ]]; then
  PENDING_NOTE="
## Pending KG enrich
A git commit completed since last KG rebuild. When changelog is updated for a **stable** fix:
\`scripts/bin/kg-enrich.sh\` or \`scripts/bin/kg-switch.sh\`
"
fi

UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
{
  cat <<EOF
# Workspace KG state (auto-generated — do not edit)

Updated: ${UTC}

## Freshness
\`\`\`
${FRESH}
\`\`\`

## Watermark (summary)
\`\`\`
${WM}
\`\`\`
${PENDING_NOTE}
## Self-learning loop
Ship fix → \`cursor-bundle/brain/changelog/CHANGELOG.md\` → \`scripts/bin/kg-switch.sh\` → \`kg cases <flow>\`

Rule: \`.cursor/rules/30-kg-discipline.mdc\` · Branch safety: \`cursor-bundle/kg/BRANCH-SAFETY.md\`
EOF
  if [[ -n "$TELEMETRY" ]]; then
    echo ""
    echo "$TELEMETRY"
  fi
} >"$STATE"
