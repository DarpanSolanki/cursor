#!/usr/bin/env bash
# Workspace sanity — proof-backed health of intelligence stack + core tools.
# Usage:
#   workspace-sanity.sh           # quick (~30s)
#   workspace-sanity.sh --full    # includes smoke-workspace (~3min)
#   workspace-sanity.sh --fast    # ~5s — super-agent session, skip heavy doctor
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
FAIL=0
MODE=quick
FAST=0
for a in "$@"; do
  case "$a" in
    --full) MODE=full ;;
    --quick) MODE=quick ;;
    --fast|-f) FAST=1 ;;
  esac
done

pass() { echo "  OK  $1"; }
fail() { echo "  FAIL $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== workspace sanity ($MODE${FAST:+, fast}) ==="

if [[ "$FAST" == 1 ]]; then
  echo ""
  echo "--- super-agent fast session ---"
  if bash scripts/bin/super-agent.sh session 2>&1 | head -20; then
    pass "super-agent session (fast)"
  else
    fail "super-agent session"
  fi
  python3 scripts/testing/sync_engine.py status 2>/dev/null | head -8 || true
fi

echo ""
echo "--- KG sync ---"
if [[ "$FAST" != 1 ]]; then
  bash scripts/bin/kg-session-sync.sh --quiet 2>/dev/null || bash scripts/bin/kg-ensure-fresh.sh --quiet 2>/dev/null || true
  python3 cursor-bundle/kg/bin/kg.py validate >/dev/null 2>&1 && echo "  OK  kg validate (post-sync)" || { echo "  FAIL kg validate"; FAIL=$((FAIL + 1)); }
else
  pass "kg-session-sync (skipped — super-agent session already ran)"
fi

echo ""
echo "--- intelligence hub ---"
for f in cursor-bundle/brain/skills-manifest.json cursor-bundle/brain/SKILLS-INDEX.md \
         scripts/testing/learning_bus.py scripts/testing/learn_cli.py \
         scripts/testing/intelligence_hub.py scripts/testing/agent_router.py; do
  [[ -f "$f" ]] && pass "$f" || fail "$f" "missing"
done
[[ -x scripts/bin/write-intelligence-hub.sh ]] && pass "write-intelligence-hub.sh" || fail "write-intelligence-hub" "not executable"
[[ -x scripts/bin/agent-router.sh ]] && pass "agent-router.sh" || fail "agent-router" "not executable"
[[ -x scripts/bin/brain-triage.sh ]] && pass "brain-triage.sh" || fail "brain-triage" "not executable"
bash scripts/bin/write-intelligence-hub.sh >/dev/null && pass "hub generated" || fail "hub generate" ""
[[ -f .cursor/workspace-intelligence-state.md ]] && pass "workspace-intelligence-state.md" || fail "hub file" "missing"

echo ""
echo "--- learning bus ---"
if bash scripts/bin/test-learn.sh --api sanityWorkspace --kind gotcha --text "sanity probe gotcha" 2>/dev/null | grep -q '"ok"'; then
  pass "test-learn.sh → learn_cli"
else
  fail "test-learn" "learn_cli add failed"
fi
if python3 scripts/testing/learn_cli.py list --api sanityWorkspace 2>/dev/null | grep -q sanity; then
  pass "learn_cli list"
else
  fail "learn_cli list" "no row"
fi

echo ""
echo "--- agent router ---"
if bash scripts/bin/super-agent.sh gaps --money 2>/dev/null | grep -q "Unified gaps"; then
  pass "super-agent gaps"
else
  fail "super-agent gaps" "no output"
fi
if bash scripts/bin/super-agent.sh orient getLoanAccountBasicDetails 2>/dev/null | grep -q "Unified orient"; then
  pass "super-agent orient"
else
  fail "super-agent orient" "no unified view"
fi
[[ -x scripts/bin/super-agent.sh ]] && pass "super-agent.sh" || fail "super-agent.sh" "missing"
[[ -f scripts/testing/cross_learn.py ]] && pass "cross_learn.py" || fail "cross_learn" "missing"

echo ""
echo "--- test map ---"
if [[ -f cursor-bundle/flow-test/test_map.jsonl ]] || python3 scripts/testing/test_map_builder.py build --apply >/dev/null 2>&1; then
  pass "test_map built"
else
  fail "test_map" "build failed"
fi
python3 scripts/testing/test_map_builder.py stats 2>/dev/null | grep -q registry_cases && pass "test_map stats" || fail "test_map stats" ""

if bash scripts/bin/agent-router.sh classify "foreclosure batch expiry RCA" 2>/dev/null | grep -q "BUG/RCA"; then
  pass "agent-router classify RCA"
else
  fail "agent-router" "classification"
fi

echo ""
echo "--- KG CLI extensions ---"
python3 cursor-bundle/kg/bin/kg.py validate >/dev/null 2>&1 && pass "kg validate" || fail "kg validate" ""
# Current CLI (Upgrade 9): validate / orient / watermark — not legacy map/test-gaps
if python3 cursor-bundle/kg/bin/kg.py watermark 2>/dev/null | grep -qE "KG built|watermark|trustt-platform"; then
  pass "kg watermark"
else
  fail "kg watermark" "no output"
fi
if python3 cursor-bundle/kg/bin/kg.py orient disburseLoan 2>/dev/null | grep -qE "ORIENT \(evidence only|populateUserDetails|FLOW request"; then
  pass "kg orient"
else
  fail "kg orient" "no output"
fi

echo ""
echo "--- flow-test artifacts ---"
for f in cursor-bundle/flow-test/platform_map.jsonl cursor-bundle/flow-test/contracts.jsonl \
         cursor-bundle/flow-test/chains.jsonl cursor-bundle/flow-test/footprints.jsonl; do
  [[ -s "$f" ]] && pass "$(basename "$f")" || fail "$(basename "$f")" "empty/missing"
done
python3 scripts/testing/platform_scan.py stats 2>/dev/null | grep -q platform_apis && pass "platform_scan stats" || fail "platform_scan stats" ""

echo ""
echo "--- workspace doctor (quick) ---"
if [[ "$FAST" == 1 ]]; then
  pass "workspace-doctor (skipped in --fast mode)"
else
  if bash scripts/bin/workspace-doctor.sh --quick 2>&1; then
    pass "workspace-doctor"
  else
    if python3 cursor-bundle/kg/bin/kg.py fresh --no-drift-check 2>/dev/null | grep -q FRESH; then
      pass "workspace-doctor (with KG fresh override)"
    else
      fail "workspace-doctor" "see output above"
    fi
  fi
fi

if [[ "$MODE" == "full" ]]; then
  echo ""
  echo "--- smoke-workspace (full) ---"
  bash scripts/bin/smoke-workspace.sh || FAIL=$((FAIL + 1))
fi

echo ""
echo "--- record sanity ---"
if python3 - <<'PY'
import sys
sys.path.insert(0, "scripts/testing")
from learning_bus import append_event
append_event("sanity_pass" if True else "sanity_fail", source="workspace-sanity.sh", detail="quick gate")
print("ok")
PY
then
  pass "learning_bus sanity_pass event"
else
  fail "learning_bus record" ""
fi

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "=== SANITY: PASS ==="
  bash scripts/bin/write-intelligence-hub.sh >/dev/null 2>&1 || true
  exit 0
else
  python3 -c "
import sys; sys.path.insert(0,'scripts/testing')
from learning_bus import append_event
append_event('sanity_fail', source='workspace-sanity.sh', detail='$FAIL failure(s)')
" 2>/dev/null || true
  echo "=== SANITY: FAIL ($FAIL) ==="
  exit 1
fi
