#!/usr/bin/env bash
# Record a gap/risk discovered during analysis or implementation (self-learning inbox).
# Triage into .cursor/gaps-and-risks.md when verified — do not auto-promote to open gaps.
#
# Usage:
#   brain-gap-capture.sh --title "short title" --risk High|Medium|Low --evidence "path:lines" \\
#     [--api apiName] [--detail "longer context"]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
INBOX="$ROOT/cursor-bundle/brain/discoveries/INBOX.md"
AUDIT="$ROOT/.cursor/changelog.md"
mkdir -p "$(dirname "$INBOX")"

TITLE="" RISK="" EVIDENCE="" API="" DETAIL=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --title) TITLE="$2"; shift 2 ;;
    --risk) RISK="$2"; shift 2 ;;
    --evidence) EVIDENCE="$2"; shift 2 ;;
    --api) API="$2"; shift 2 ;;
    --detail) DETAIL="$2"; shift 2 ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

[[ -n "$TITLE" && -n "$RISK" && -n "$EVIDENCE" ]] || {
  echo "Required: --title --risk --evidence" >&2
  exit 2
}
case "$RISK" in High|Medium|Low) ;; *)
  echo "--risk must be High, Medium, or Low" >&2
  exit 2
  ;;
esac

UTC=$(date -u +%Y-%m-%dT%H:%M:%SZ)
DATE=$(date -u +%Y-%m-%d)
ID="DISC-$(date -u +%Y%m%d-%H%M%S)"

if [[ ! -f "$INBOX" ]]; then
  cat >"$INBOX" <<'HDR'
# Discovery inbox (auto-captured — triage into gaps-and-risks.md)

Agents append here via `scripts/bin/brain-gap-capture.sh`. **Not** production gap registry until reviewed.

HDR
fi

{
  echo ""
  echo "## $ID — $TITLE"
  echo "- **Captured:** $UTC"
  echo "- **Risk (provisional):** $RISK"
  echo "- **Evidence:** $EVIDENCE"
  [[ -n "$API" ]] && echo "- **apiName:** $API"
  [[ -n "$DETAIL" ]] && echo "- **Detail:** $DETAIL"
  echo "- **Triage:** add to \`.cursor/gaps-and-risks.md\` if confirmed; else mark dismissed below."
  echo ""
} >>"$INBOX"

if [[ -f "$AUDIT" ]]; then
  TMP=$(mktemp)
  {
    head -n 8 "$AUDIT"
    echo ""
    echo "## $DATE | workspace | discovery | $ID | $TITLE ($RISK)"
    echo "Evidence: $EVIDENCE${API:+; api=$API}. Inbox: cursor-bundle/brain/discoveries/INBOX.md"
    echo ""
    tail -n +9 "$AUDIT"
  } >"$TMP"
  mv "$TMP" "$AUDIT"
fi

echo "[brain-gap-capture] $ID → $INBOX"
python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "$ROOT/scripts/testing")
from learning_bus import append_event
append_event("gap_discovered", source="brain-gap-capture.sh", api="$API" or None,
             detail="$TITLE", evidence="$EVIDENCE", meta={"disc_id": "$ID", "risk": "$RISK"})
PY
echo "Next: verify in code/DB, then promote to .cursor/gaps-and-risks.md or dismiss in INBOX."
