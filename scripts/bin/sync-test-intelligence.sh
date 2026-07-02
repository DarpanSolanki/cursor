#!/usr/bin/env bash
# Test intelligence sync — fingerprint-gated (fast default).
#
# Usage:
#   sync-test-intelligence.sh              # fast — rebuild only stale layers
#   sync-test-intelligence.sh --full       # always rebuild all steps
#   sync-test-intelligence.sh --kg         # fast + KG via sync-intelligence --quick
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BIN="$ROOT/scripts/bin"
FAIL=0
MODE=fast

for a in "$@"; do
  case "$a" in
    --kg) WITH_KG=1 ;;
    --full|-f) MODE=full ;;
    --fast) MODE=fast ;;
  esac
done
WITH_KG="${WITH_KG:-0}"

if [[ "$MODE" == "fast" ]]; then
  python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet || FAIL=1
  python3 "$ROOT/scripts/testing/lib/validate_registry.py" || FAIL=1
  if [[ "$WITH_KG" == 1 ]]; then
    bash "$BIN/sync-intelligence.sh" --quick || FAIL=1
  fi
  if [[ "$FAIL" == 0 ]]; then
    echo "sync-test-intelligence: PASS (fast)"
    python3 "$ROOT/scripts/testing/test_map_builder.py" stats 2>/dev/null || true
  else
    echo "sync-test-intelligence: FAIL (fast)"
    exit 1
  fi
  exit 0
fi

step() { echo ""; echo "══ $1 ══"; }

step "1/6 FTG enrich"
python3 "$ROOT/scripts/testing/ftg.py" enrich --apply || FAIL=1

step "2/6 Footprints"
python3 "$ROOT/scripts/testing/footprint_builder.py" build --apply || FAIL=1

step "3/6 Test map"
python3 "$ROOT/scripts/testing/test_map_builder.py" build --apply || FAIL=1

step "4/6 Registry validate"
python3 "$ROOT/scripts/testing/lib/validate_registry.py" || FAIL=1

step "5/6 Gates"
python3 "$ROOT/scripts/testing/ftg.py" validate || FAIL=1

step "6/6 Hub + cross-learn"
python3 -c "import sys; sys.path.insert(0,'scripts/testing'); from cross_learn import propagate_learnings_to_hints; propagate_learnings_to_hints()" || true
bash "$BIN/write-intelligence-hub.sh" --fast >/dev/null || FAIL=1
python3 "$ROOT/scripts/testing/sync_engine.py" status >/dev/null 2>&1 || true

if [[ "$WITH_KG" == 1 ]]; then
  bash "$BIN/sync-intelligence.sh" --quick || FAIL=1
fi

if [[ "$FAIL" != 0 ]]; then
  echo "sync-test-intelligence: FAIL (full)"
  exit 1
fi
echo "sync-test-intelligence: PASS (full)"
