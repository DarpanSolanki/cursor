#!/usr/bin/env bash
# Master intelligence sync — contracts + chains + footprints + FTG + KG gates.
# Run after branch checkout, orchestration change, or shipped fix+test.
#
# Usage:
#   scripts/bin/sync-intelligence.sh           # full sync (cache KG if branch unchanged)
#   scripts/bin/sync-intelligence.sh --force   # force KG rebuild
#   scripts/bin/sync-intelligence.sh --quick   # skip KG rebuild
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BIN="$ROOT/scripts/bin"
KG="$ROOT/cursor-bundle/kg/bin"
FAIL=0

FORCE=0
QUICK=0
for a in "$@"; do
  case "$a" in
    --force|-f) FORCE=1 ;;
    --quick|-q) QUICK=1 ;;
  esac
done

step() { echo ""; echo "══ $1 ══"; }

step "1/8 Parallel platform scan (map + contracts + chains)"
python3 "$ROOT/scripts/testing/platform_scan.py" run --workers "${SCAN_WORKERS:-4}" || FAIL=1

step "2/8 Branch watermark (target: mfi_integration_v3.3.1.1)"
if [[ -f "$ROOT/cursor-bundle/flow-test/branch_watermark.json" ]]; then
  python3 - <<'PY'
import json, sys
from pathlib import Path
wm = json.loads(Path("cursor-bundle/flow-test/branch_watermark.json").read_text())
bad = [r for r,v in wm.get("repos",{}).items() if not v.get("aligned")]
if bad:
    print("⚠ Branch drift (scan still proceeds; align for production-accurate chains):")
    for r in bad:
        v = wm["repos"][r]
        print(f"   {r}: {v.get('branch')} @ {v.get('head')} (upstream {v.get('upstream_v3.3.1.1')})")
else:
    print("✓ Core repos aligned with mfi_integration_v3.3.1.1")
PY
fi

step "3/8 Contract rescan (FTG links refreshed)"
python3 "$ROOT/scripts/testing/contract_graph.py" scan || FAIL=1

step "4/8 API chains (processors + internal APIs → chains.jsonl)"
# Prefer kg.jsonl for processor order; build chains after optional KG restore
if [[ "$QUICK" == 0 && "$FORCE" == 0 ]]; then
  bash "$BIN/kg-switch.sh" --quiet 2>/dev/null || true
fi
python3 "$KG/build_api_chains.py" || FAIL=1

step "5/8 Footprints (FTG + chains + contracts + precedents)"
python3 "$ROOT/scripts/testing/footprint_builder.py" build --apply || FAIL=1

step "5b/8 Test intelligence map (fast incremental)"
bash "$BIN/sync-test-intelligence.sh" --fast 2>/dev/null || python3 "$ROOT/scripts/testing/test_map_builder.py" build --apply || FAIL=1

step "6/8 FTG enrich (sources + registry + unit tests)"
python3 "$ROOT/scripts/testing/ftg.py" enrich --apply || FAIL=1
python3 "$ROOT/scripts/testing/footprint_builder.py" build --apply || true

step "7/8 Validation gates"
python3 "$ROOT/scripts/testing/ftg.py" validate || FAIL=1
python3 "$KG/kg_validate.py" 2>/dev/null || { echo "⚠ kg.db missing/stale — run with --force"; }

if [[ "$QUICK" == 0 ]]; then
  step "8/8 KG rebuild (includes platform_map + testing_kg)"
  if [[ "$FORCE" == 1 ]]; then
    bash "$BIN/kg-switch.sh" --force || FAIL=1
  else
    bash "$BIN/kg-switch.sh" --quiet || bash "$BIN/kg-switch.sh" --force || FAIL=1
  fi
  python3 "$KG/build_api_chains.py" || true
  python3 "$ROOT/scripts/testing/footprint_builder.py" build --apply || true
else
  echo "══ 8/8 KG rebuild skipped (--quick) ══"
fi

step "Summary"
python3 "$ROOT/scripts/testing/contract_graph.py" stats || true
python3 "$ROOT/scripts/testing/ftg.py" gaps || true
python3 "$ROOT/scripts/testing/contract_graph.py" gaps || true
python3 "$ROOT/scripts/testing/footprint_builder.py" list || true
python3 "$KG/kg.py" fresh --no-drift-check 2>/dev/null || true
bash "$BIN/write-intelligence-hub.sh" --fast >/dev/null 2>&1 || true

if [[ "$FAIL" != 0 ]]; then
  echo ""
  echo "sync-intelligence: FAIL — fix gates above"
  exit 1
fi
echo ""
echo "sync-intelligence: PASS"
echo "Next fix+test: append sources.jsonl → ftg enrich --apply → sync-intelligence.sh --quick"
