#!/usr/bin/env bash
# Write .cursor/workspace-kg-state.md from current kg.db (no rebuild / no kg-switch).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
cd "$ROOT"
KG="python3 cursor-bundle/kg/bin/kg.py"
STATE=".cursor/workspace-kg-state.md"
PENDING=".cursor/.pending-kg-rebuild"
mkdir -p .cursor

FRESH=$($KG fresh --no-drift-check 2>&1 || echo "KG fresh check failed")
WM=$($KG watermark --no-drift-check 2>&1 | head -20 || echo "KG watermark failed")
PENDING_NOTE=""
if [[ -f "$PENDING" ]]; then
  PENDING_NOTE="
## Pending KG enrich
A git commit completed since last KG rebuild. When changelog is updated for a **stable** fix:
\`scripts/bin/kg-enrich.sh\` or \`scripts/bin/kg-switch.sh\`
"
fi

UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
cat >"$STATE" <<EOF
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

Rule: \`.cursor/rules/self-learning-kg.mdc\` · Branch safety: \`cursor-bundle/kg/BRANCH-SAFETY.md\`
EOF
