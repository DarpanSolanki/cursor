#!/usr/bin/env bash
# After a fix + test on a money path — capture full API footprint for the suite.
# Usage:
#   scripts/bin/capture-flow.sh --ftg ftf:foreclosure.batch_expiry_lms --jira SDCP-10400 \
#     --test "ExpireLoanForeclosureServiceTest" --verified 2026-06-19
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FTG=""
JIRA=""
TEST=""
VERIFIED="$(date -u +%Y-%m-%d)"
NOTE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --ftg) FTG="$2"; shift 2 ;;
    --jira) JIRA="$2"; shift 2 ;;
    --test) TEST="$2"; shift 2 ;;
    --verified) VERIFIED="$2"; shift 2 ;;
    --note) NOTE="$2"; shift 2 ;;
    *) echo "Unknown: $1"; exit 1 ;;
  esac
done

[[ -n "$FTG" ]] || { echo "Required: --ftg ftf:..."; exit 1; }
FID="${FTG#ftf:}"

SOURCES="$ROOT/cursor-bundle/flow-test/sources.jsonl"
LINE=$(python3 - <<PY
import json
ftg = "$FTG"
test = "$TEST"
jira = "$JIRA"
verified = "$VERIFIED"
note = "$NOTE"
row = {
  "source": "capture",
  "id": f"capture.{fid.replace(':', '_')}.{verified}",
  "type": "verified_fix",
  "ftg_id": ftg,
  "tier": "local",
  "coverage": "partial",
  "verified": verified,
}
if test:
    row["unit"] = test
if jira:
    row["precedents"] = [jira]
if note:
    row["note"] = note
print(json.dumps(row, separators=(",", ":")))
PY
)

echo "$LINE" >> "$SOURCES"
echo "Appended capture row to sources.jsonl"
python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "$ROOT/scripts/testing")
from learning_bus import append_event
append_event("fix_captured", source="capture-flow.sh", detail="ftg=$FTG",
             meta={"ftg": "$FTG", "jira": "$JIRA", "test": "$TEST"})
PY
bash "$ROOT/scripts/bin/super-agent.sh" sync 2>/dev/null || python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet 2>/dev/null || true
echo "Capture complete. Footprint: python3 scripts/testing/footprint_builder.py show $FTG"
