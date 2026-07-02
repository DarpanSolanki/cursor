#!/usr/bin/env bash
# Prepend a 2-line changelog entry; refresh flow precedents only when --kg-flow.
#
# Usage:
#   changelog-add.sh --kg-flow "DATE | acct \`sha\` | service | branch | kg-flow | title" "detail with apiName…"
#   changelog-add.sh "DATE | … | kb-only | title" "human audit only — no KG case"
#   changelog-add.sh --dry-run "header" "detail"
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT="$(cd "$BUNDLE/.." && pwd)"
CHANGELOG="$BUNDLE/brain/changelog/CHANGELOG.md"
DRY=0
KG_FLOW=0
[[ "${1:-}" == "--dry-run" ]] && { DRY=1; shift; }
[[ "${1:-}" == "--kg-flow" ]] && { KG_FLOW=1; shift; }

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 [--kg-flow] [--dry-run] \"## header\" \"detail\"" >&2
  echo "  --kg-flow  index as flow precedent (kg cases); omit for audit-only / kb-only entries" >&2
  exit 2
fi
HEADER="$1"
DETAIL="$2"
[[ "$HEADER" != "## "* ]] && HEADER="## $HEADER"
if [[ "$KG_FLOW" == 1 ]] && ! echo "$HEADER" | grep -qi 'kg-flow'; then
  # insert kg-flow tag after branch field when using --kg-flow flag
  HEADER="$(echo "$HEADER" | sed -E 's/(\| [^|]+)$/| kg-flow \1/')"
fi

TMP=$(mktemp)
{
  head -n 6 "$CHANGELOG"
  echo ""
  echo "$HEADER"
  echo "$DETAIL"
  echo ""
  echo "---"
  echo ""
  tail -n +7 "$CHANGELOG"
} >"$TMP"

if [[ "$DRY" == 1 ]]; then
  echo "[dry-run] would prepend to $CHANGELOG:"
  head -n 20 "$TMP"
  rm -f "$TMP"
  exit 0
fi

mv "$TMP" "$CHANGELOG"
echo "[changelog-add] prepended to $CHANGELOG"

if echo "$HEADER" | grep -qiE 'kg-flow|KG-FLOW:' || echo "$DETAIL" | grep -q '^KG-FLOW:'; then
  cd "$ROOT"
  KG_DB="$BUNDLE/kg/data/kg.db"
  if [[ -f "$KG_DB" ]] && python3 "$SCRIPT_DIR/kg.py" doctor 2>&1 | grep -q "WATERMARK: in sync"; then
    python3 "$SCRIPT_DIR/refresh_cases.py"
    echo "[changelog-add] flow precedents refreshed (--kg-flow)"
  else
    bash "$SCRIPT_DIR/build.sh"
    echo "[changelog-add] full KG rebuild (graph drift)"
  fi
else
  echo "[changelog-add] audit-only — no KG refresh (tag | kg-flow | or use --kg-flow to index)"
fi
rm -f "$ROOT/.cursor/.pending-kg-rebuild" 2>/dev/null || true
echo "[changelog-add] try: python3 cursor-bundle/kg/bin/kg.py cases <apiName>"
