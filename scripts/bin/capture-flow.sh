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
fid = "$FID"
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

# Dev-Test ADF export for Jira handoff (Upgrade 7) — does NOT post
PROOF_DIR="$ROOT/scripts/scratch/jira-handoff"
mkdir -p "$PROOF_DIR"
ADF_OUT="$PROOF_DIR/${JIRA:-NOJIRA}-dev-test.adf.json"
python3 - "$ADF_OUT" "$FTG" "$JIRA" "$TEST" "$VERIFIED" <<'PY'
import json, sys
from pathlib import Path
out, ftg, jira, test, verified = sys.argv[1:6]
doc = {
  "version": 1,
  "type": "doc",
  "content": [
    {"type": "heading", "attrs": {"level": 3}, "content": [{"type": "text", "text": "Dev Test evidence"}]},
    {"type": "table", "content": [
      {"type": "tableRow", "content": [
        {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Field"}]}]},
        {"type": "tableHeader", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Value"}]}]},
      ]},
      {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "FTG"}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": ftg}]}]},
      ]},
      {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Jira"}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": jira or "-"}]}]},
      ]},
      {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Test"}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": test or "-"}]}]},
      ]},
      {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Verified"}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": verified}]}]},
      ]},
      {"type": "tableRow", "content": [
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Result"}]}]},
        {"type": "tableCell", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "PASS (captured)"}]}]},
      ]},
    ]},
    {"type": "paragraph", "content": [{"type": "text", "text": "Post via jira-handoff.sh --dry-run then explicit user go + MCP."}]},
  ],
}
Path(out).write_text(json.dumps(doc, indent=2), encoding="utf-8")
print(out)
PY
echo "Dev-Test ADF → $ADF_OUT"
if [[ -n "$JIRA" ]]; then
  bash "$ROOT/scripts/bin/jira-handoff.sh" --dry-run --jira "$JIRA" --adf "$ADF_OUT" || true
fi

python3 - <<PY 2>/dev/null || true
import sys
sys.path.insert(0, "$ROOT/scripts/testing")
from learning_bus import append_event
append_event("fix_captured", source="capture-flow.sh", detail="ftg=$FTG",
             meta={"ftg": "$FTG", "jira": "$JIRA", "test": "$TEST"})
PY
bash "$ROOT/scripts/bin/super-agent.sh" sync 2>/dev/null || python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet 2>/dev/null || true
echo "Capture complete. Footprint: python3 scripts/testing/footprint_builder.py show $FTG"
