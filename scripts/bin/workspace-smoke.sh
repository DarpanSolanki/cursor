#!/usr/bin/env bash
# Workspace smoke — verify KG, hooks, registry, ship gates, hygiene, optional quick ntest.
# Usage:
#   workspace-smoke.sh              # fast (~30–60s)
#   workspace-smoke.sh --full       # + health probes + disburse-quick if services up
#   workspace-smoke.sh --quick        # gates only, no ntest flows
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GATE="$ROOT/scripts/lib/ship_push_gate.py"
FULL=0
QUICK=0
FAIL=0

for a in "$@"; do
  case "$a" in
    --full) FULL=1 ;;
    --quick) QUICK=1 ;;
    -h|--help)
      sed -n '2,6p' "$0"
      exit 0
      ;;
  esac
done

pass() { echo "  ✓ $*"; }
fail() { echo "  ✗ $*" >&2; FAIL=$((FAIL + 1)); }
warn() { echo "  ⚠ $*"; }

echo "=== workspace smoke ==="

# 1 — KG
if python3 "$ROOT/cursor-bundle/kg/bin/kg.py" validate >/dev/null 2>&1; then
  pass "kg validate"
else
  fail "kg validate"
fi
if bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet 2>/dev/null; then
  pass "kg fresh"
else
  fail "kg fresh — run: scripts/bin/kg-switch.sh"
fi

# 2 — hooks + manifests
[[ -f "$ROOT/.cursor/hooks.json" ]] && pass "hooks.json" || fail "hooks.json missing"
[[ -f "$ROOT/cursor-bundle/brain/skills-manifest.json" ]] && pass "skills-manifest" || fail "skills-manifest"
[[ -x "$ROOT/scripts/bin/workspace-close.sh" ]] && pass "workspace-close executable" || fail "workspace-close"
[[ -x "$ROOT/scripts/bin/fwd-port.sh" ]] && pass "fwd-port executable" || fail "fwd-port executable"
[[ -x "$ROOT/cursor-bundle/kg/bin/fwd-port.sh" ]] && pass "kg fwd-port wrapper executable" \
  || fail "kg fwd-port wrapper executable"
if bash "$ROOT/cursor-bundle/kg/bin/fwd-port.sh" --help >/dev/null 2>&1 \
  || bash "$ROOT/scripts/bin/fwd-port.sh" --help >/dev/null 2>&1; then
  pass "fwd-port --help"
else
  fail "fwd-port --help"
fi
if python3 "$ROOT/cursor-bundle/kg/bin/kg.py" fixed-elsewhere --help >/dev/null 2>&1; then
  pass "kg fixed-elsewhere --help"
else
  fail "kg fixed-elsewhere --help"
fi
if PYTHONPATH="$ROOT/scripts/lib" python3 -m unittest scripts.lib.test_branch_train >/dev/null 2>&1; then
  pass "cross-branch train tests"
else
  fail "cross-branch train tests"
fi
if PYTHONPATH="$ROOT/cursor-bundle/kg/bin:$ROOT/scripts/lib" \
  python3 -m unittest scripts.lib.test_build_cases >/dev/null 2>&1; then
  pass "build_cases header parse tests"
else
  fail "build_cases header parse tests"
fi

# 3 — registry + ship gate lib
if python3 "$ROOT/scripts/testing/ntest.py" validate >/dev/null 2>&1; then
  pass "ntest registry validate"
else
  fail "ntest registry validate"
fi
python3 "$GATE" --satisfied >/dev/null 2>&1 && pass "ship_push_gate --satisfied (no pending or already closed)" \
  || pass "ship_push_gate (pending work exists — expected if unclosed edits)"

# 4 — enrichment audit (non-blocking)
if bash "$ROOT/scripts/bin/enrichment-audit.sh" 2>&1 | grep -q "enrichment audit: PASS"; then
  pass "enrichment audit"
else
  warn "enrichment audit has warnings (see above if run with -v)"
fi

# 5 — hygiene
if bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null; then
  pass "workspace hygiene"
else
  bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
  bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null && pass "hygiene after clean" || fail "hygiene"
fi

# 6 — intel sync fast
if python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet 2>/dev/null; then
  pass "intel fast-sync"
else
  warn "intel fast-sync failed (non-fatal)"
fi

# 7 — learnings.jsonl readable (always absolute ROOT — never cwd-relative)
if python3 - <<PY 2>/dev/null
import json
from pathlib import Path
p = Path("$ROOT/cursor-bundle/brain/testing/learnings.jsonl")
if not p.is_file():
    raise SystemExit(f"missing {p}")
for line in p.read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    o = json.loads(line)
    if o.get("kind") == "meta":
        continue
    text = o.get("text") or o.get("lesson") or ""
    assert text, f"missing text/lesson: {o}"
print("ok")
PY
then
  pass "learnings.jsonl schema"
else
  fail "learnings.jsonl schema"
fi

if [[ "$QUICK" -eq 1 ]]; then
  echo "=== workspace smoke: $([[ $FAIL -eq 0 ]] && echo PASS || echo FAIL) (quick) ==="
  exit "$FAIL"
fi

# 8 — workspace-close cached path (should be instant if nothing pending)
t0=$(date +%s)
if bash "$ROOT/scripts/bin/workspace-close.sh" --from-pending 2>&1 | grep -qE 'PASS \(cached\)|PASS \(nothing pending\)|workspace-close: PASS'; then
  dt=$(($(date +%s) - t0))
  pass "workspace-close (${dt}s)"
else
  fail "workspace-close"
fi

if [[ "$FULL" -eq 1 ]]; then
  echo "→ full smoke: health + disburse-quick"
  for hid in health.accounting health.actor; do
    if bash "$ROOT/scripts/bin/ntest.sh" run "$hid" 2>/dev/null; then
      pass "ntest $hid"
    else
      warn "ntest $hid failed (service may be down)"
    fi
  done
  if [[ -x "$ROOT/scripts/bin/disburse-quick.sh" ]]; then
    if bash "$ROOT/scripts/bin/disburse-quick.sh" 2>/dev/null; then
      pass "disburse-quick"
    else
      warn "disburse-quick failed (check accounting + DB)"
    fi
  fi
fi

echo "=== workspace smoke: $([[ $FAIL -eq 0 ]] && echo PASS || echo FAIL) (${FULL:+full }${QUICK:+quick }default) ==="
exit "$FAIL"
