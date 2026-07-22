#!/usr/bin/env bash
# Verify post-ship knowledge closure — run before declaring a money-path fix "done".
#
# Profiles (tier-aware via workspace-close):
#   minimal   — workspace tier: KG fresh + hygiene (+ changelog pending markers)
#   standard  — service tier: + hub, skills manifest, intel fingerprint
#   full      — money tier: everything including kg-flow sha + learning_bus
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAIL=0
PROFILE="${SHIP_GATE_PROFILE:-standard}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --profile) PROFILE="$2"; shift 2 ;;
    --minimal) PROFILE=minimal; shift ;;
    --full) PROFILE=full; shift ;;
    -h|--help)
      sed -n '2,8p' "$0"
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

warn() { echo "WARN: $*" >&2; }
fail() { echo "FAIL: $*" >&2; FAIL=1; }
ok()   { echo "OK: $*"; }

echo "=== post-ship knowledge gate (profile=$PROFILE) ==="

# 1 — no (pending) in recent audit changelog (all profiles)
if grep -q '(pending)' "$ROOT/.cursor/changelog.md" 2>/dev/null; then
  fail ".cursor/changelog.md still contains '(pending)' — close gaps/flows then remove pending markers"
else
  ok "no (pending) in .cursor/changelog.md"
fi

if [[ "$PROFILE" == "minimal" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    if bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet 2>/dev/null; then
      ok "KG FRESH"
    else
      fail "KG not FRESH — run: scripts/bin/kg-ensure-fresh.sh"
    fi
  fi
  if bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null; then
    ok "workspace hygiene clean"
  else
    warn "hygiene issues — auto-clean"
    bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
    bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null && ok "workspace hygiene after --clean" \
      || warn "hygiene issues remain"
  fi
  if [[ "$FAIL" -ne 0 ]]; then
    echo "=== post-ship knowledge gate: FAIL ===" >&2
    exit 1
  fi
  echo "=== post-ship knowledge gate: PASS ==="
  exit 0
fi

# standard + full
if [[ -f "$ROOT/.cursor/workspace-intelligence-state.md" ]]; then
  ok "workspace-intelligence-state.md present"
else
  fail "missing hub — run: scripts/bin/write-intelligence-hub.sh"
fi

if [[ -f "$ROOT/cursor-bundle/brain/skills-manifest.json" ]]; then
  ok "skills-manifest.json present"
else
  fail "missing skills-manifest.json"
fi

if command -v python3 >/dev/null 2>&1; then
  if bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet 2>/dev/null; then
    ok "KG FRESH"
  else
    fail "KG not FRESH — run: scripts/bin/kg-ensure-fresh.sh"
    python3 "$ROOT/cursor-bundle/kg/bin/kg.py" fresh 2>&1 | head -5 >&2 || true
  fi
fi

if [[ -f "$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md" ]]; then
  if grep -q '| kg-flow |' "$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md"; then
    ok "brain CHANGELOG has kg-flow rows"
  else
    warn "no kg-flow rows in brain CHANGELOG (OK if kb-only / no flow change)"
  fi
else
  fail "missing cursor-bundle/brain/changelog/CHANGELOG.md"
fi

if [[ "$PROFILE" == "full" ]]; then
  ACCT="$ROOT/trustt-platform-accounting"
  if [[ -d "$ACCT/.git" ]]; then
    head_sha="$(git -C "$ACCT" rev-parse --short=10 HEAD 2>/dev/null || true)"
    top_kg="$(grep -m1 'kg-flow' "$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md" 2>/dev/null || true)"
    if [[ -n "$head_sha" && -n "$top_kg" && "$top_kg" == *"acct \`$head_sha"* ]]; then
      ok "top kg-flow row matches accounting HEAD ($head_sha)"
    elif [[ -n "$head_sha" && -n "$top_kg" ]]; then
      warn "top kg-flow sha may not match accounting HEAD ($head_sha) — verify brain CHANGELOG order"
    fi
  fi

  if [[ -f "$ROOT/scripts/testing/sync_engine.py" ]]; then
    stale_n="$(python3 "$ROOT/scripts/testing/sync_engine.py" status 2>/dev/null | grep -c STALE || true)"
    if [[ "${stale_n:-0}" -gt 0 ]]; then
      warn "intel layers STALE ($stale_n) — run: bash scripts/bin/super-agent.sh sync --full"
    else
      ok "intel layers fresh (fingerprint)"
    fi
  fi
  if python3 - <<'PY' 2>/dev/null
import sys
sys.path.insert(0, "scripts/testing")
from learning_bus import load_signal_events
rows = load_signal_events(3)
sys.exit(0 if rows else 1)
PY
  then
    ok "learning_bus has recent signal events"
  else
    warn "no recent signal events on learning_bus (OK if kb-only ship)"
  fi

  # Companion knowledge for DCF / DeathForeclosure money ships
  if python3 "$ROOT/scripts/lib/registry_companion_gate.py" check --hard; then
    ok "DCF companion knowledge (registry/runbook/gaps) markers present"
    ok "QA-acceptance anti-patterns absent (asserts fail on QA fail mode)"
  else
    fail "registry/runbook companion stale or e2e allows QA fail mode — see feedback_qa_acceptance_not_subset_verify.md"
  fi
elif [[ -f "$ROOT/scripts/testing/sync_engine.py" ]]; then
  stale_n="$(python3 "$ROOT/scripts/testing/sync_engine.py" status 2>/dev/null | grep -c STALE || true)"
  if [[ "${stale_n:-0}" -gt 2 ]]; then
    warn "intel layers STALE ($stale_n) — optional: super-agent sync --full"
  else
    ok "intel layers acceptable for service tier"
  fi
fi

if bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null; then
  ok "workspace hygiene clean"
else
  warn "hygiene issues — auto-clean"
  bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
  if bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null; then
    ok "workspace hygiene after --clean"
  else
    warn "hygiene issues remain — move temps to scripts/scratch/<task>/ and delete when done"
  fi
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "=== post-ship knowledge gate: FAIL ===" >&2
  exit 1
fi
echo "=== post-ship knowledge gate: PASS ==="
exit 0
