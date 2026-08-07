#!/usr/bin/env bash
# beforeShellExecution — remind: changelog + KG rebuild belong in the same task turn as commit.
# Fast-exit: bash pattern check before python spawn.
set -euo pipefail
input=$(cat)
# ── fast-exit: skip python entirely unless this looks like a git commit ──
[[ "$input" =~ git ]] || { echo '{"permission":"allow"}'; exit 0; }
[[ "$input" =~ commit ]] || { echo '{"permission":"allow"}'; exit 0; }
command=$(python3 -c "import json,sys; print(json.load(sys.stdin).get('command',''))" <<<"$input")

if [[ ! "$command" =~ git[[:space:]]+commit ]]; then
  echo '{"permission":"allow"}'
  exit 0
fi

cat <<'EOF'
{
  "permission": "allow",
  "agent_message": "Same task turn as commit: prepend cursor-bundle/brain/changelog/CHANGELOG.md (2 lines), then scripts/bin/kg-enrich.sh when the fix is stable (WIP gate: 30-kg-discipline.md). Also .cursor/changelog.md for agent KB."
}
EOF
