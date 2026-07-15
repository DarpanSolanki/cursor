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
  ACCT="$ROOT/novopay-platform-accounting-v2"
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

  # Companion knowledge for DCF / DeathForeclosure money ships (WARN — harden DoD)
  if python3 - <<'PY'
import json, re, sys
from pathlib import Path
root = Path(".")
cl = (root / "cursor-bundle/brain/changelog/CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
# Top ~40 lines after first kg-flow header
m = re.search(r"^## .+?\| kg-flow \|.*?(?=^## |\Z)", cl, re.M | re.S)
block = (m.group(0) if m else cl[:2000])
keys = ("DeathForeclosure", "deathForeclosure", "loanDeathForeclosure", "DFC", "EXTRA", "labd", "force-bill", "force_bill")
if not any(k in block for k in keys):
    sys.exit(0)
reg = json.loads((root / "scripts/testing/registry.json").read_text(encoding="utf-8"))
note = (reg.get("dcf.group_parent_last_child_e2e") or {}).get("note") or ""
rb = (root / "cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md").read_text(encoding="utf-8", errors="replace")
gaps = (root / ".cursor/gaps-and-risks.md").read_text(encoding="utf-8", errors="replace")
issues = []
if "EXTRA" in block or "labd" in block or "force-bill" in block.lower() or "A2" in block:
    if "EXTRA" not in note and "labd" not in note and "A2" not in note:
        issues.append("registry dcf.group_parent_last_child_e2e note missing A2 EXTRA / B labd markers")
    if "EXTRA" not in rb or "labd" not in rb:
        issues.append("runbook sdcp-10199 missing A2 EXTRA / B labd section")
    if "GAP-075" not in gaps and "EXTRA-net" not in gaps:
        issues.append("gaps missing GAP-075 / EXTRA-net RESOLVED row")
elif "DeathForeclosure" in block or "deathForeclosure" in block or "loanDeathForeclosure" in block:
    if "dcf.group_parent_last_child_e2e" not in (root / "scripts/testing/registry.json").read_text(encoding="utf-8"):
        issues.append("DCF kg-flow but registry missing dcf.group_parent_last_child_e2e")
    if not (root / "cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md").is_file():
        issues.append("DCF kg-flow but sdcp-10199 runbook missing")
if issues:
    print("\n".join(issues))
    sys.exit(1)
sys.exit(0)
PY
  then
    ok "DCF companion knowledge (registry/runbook/gaps) markers present"
  else
    warn "DCF/money companion gap — update registry note + runbook + gaps (see feedback_post_ship_registry_runbook_gap_mandatory.md)"
    python3 - <<'PY' 2>/dev/null || true
import json, re
from pathlib import Path
root = Path(".")
cl = (root / "cursor-bundle/brain/changelog/CHANGELOG.md").read_text(encoding="utf-8", errors="replace")
m = re.search(r"^## .+?\| kg-flow \|.*?(?=^## |\Z)", cl, re.M | re.S)
block = (m.group(0) if m else cl[:2000])
reg = json.loads((root / "scripts/testing/registry.json").read_text(encoding="utf-8"))
note = (reg.get("dcf.group_parent_last_child_e2e") or {}).get("note") or ""
rb = (root / "cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md").read_text(encoding="utf-8", errors="replace")
gaps = (root / ".cursor/gaps-and-risks.md").read_text(encoding="utf-8", errors="replace")
for label, ok in [
    ("registry EXTRA/labd", "EXTRA" in note or "labd" in note or "A2" in note),
    ("runbook EXTRA+labd", "EXTRA" in rb and "labd" in rb),
    ("gaps GAP-075", "GAP-075" in gaps or "EXTRA-net" in gaps),
]:
    print(f"  companion check {label}: {'OK' if ok else 'MISSING'}")
PY
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
