#!/usr/bin/env bash
# afterFileEdit — KG incremental / fail-closed STALE (Upgrade KG-truth T4)
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat || true)
FILE=$(echo "$INPUT" | python3 -c "import json,sys
try:
 d=json.load(sys.stdin); print(d.get('file_path') or d.get('path') or '')
except Exception:
 print('')" 2>/dev/null || true)
[[ -n "$FILE" ]] || exit 0
# Only service / orch / entity paths — ignore scratch
case "$FILE" in
  *trustt-*|*novopay-*|*cursor-bundle/kg*) ;;
  *) exit 0 ;;
esac
python3 "$ROOT/cursor-bundle/kg/bin/kg_after_edit.py" "$FILE" >>"$ROOT/scripts/scratch/logs/kg-after-edit.log" 2>&1 || true
exit 0
