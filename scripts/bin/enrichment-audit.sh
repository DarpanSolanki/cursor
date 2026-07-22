#!/usr/bin/env bash
# Audit self-learning pipeline: commit ↔ changelog ↔ KG.
# Usage:
#   enrichment-audit.sh           — human-readable report (exit 0 always)
#   enrichment-audit.sh --pre-push  — exit 1 if push blocked (commit without changelog)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CHANGELOG="$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md"
KG_DB="$ROOT/cursor-bundle/kg/data/kg.db"
PENDING="$ROOT/.cursor/.pending-kg-rebuild"
PRE_PUSH=0
[[ "${1:-}" == "--pre-push" ]] && PRE_PUSH=1

issues=0
warn() { echo "  WARN: $*"; issues=$((issues + 1)); }
ok() { echo "  OK   $*"; }

echo "=== enrichment audit ==="

[[ -f "$CHANGELOG" ]] && ok "brain changelog present" || warn "missing $CHANGELOG"
[[ -f "$KG_DB" ]] && ok "kg.db present" || warn "missing kg.db — run scripts/bin/kg-enrich.sh"
[[ -x "$ROOT/scripts/bin/kg-enrich.sh" ]] && ok "kg-enrich.sh executable" || warn "kg-enrich.sh not executable"
[[ -x "$ROOT/cursor-bundle/kg/bin/changelog-add.sh" ]] && ok "changelog-add.sh executable" || warn "changelog-add.sh not executable"
[[ -f "$ROOT/.cursor/hooks.json" ]] && ok "hooks.json present" || warn "hooks.json missing — Cursor hooks inactive; copy from repo or recreate"

PENDING_SHIP="$ROOT/.cursor/.pending-ship-work.json"
PASSED_SHIP="$ROOT/.cursor/.ship-loop-passed.json"
if [[ -f "$PENDING_SHIP" ]]; then
  if python3 - <<'PY' "$PENDING_SHIP" "$PASSED_SHIP"
import json, sys
from pathlib import Path
pending = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
apis = pending.get("apis") or []
if not apis:
    sys.exit(0)
passed_p = Path(sys.argv[2])
if not passed_p.is_file():
    sys.exit(1)
passed = json.loads(passed_p.read_text(encoding="utf-8"))
if (passed.get("passed_at") or "") < pending.get("updated_at", ""):
    sys.exit(1)
if not set(apis).issubset(set(passed.get("apis") or [])):
    sys.exit(1)
PY
  then
    ok "ship-loop passed for pending APIs"
  else
    warn "pending ship work without ship-loop-gate PASS — run scripts/bin/ship-loop-gate.sh --from-pending"
    [[ "$PRE_PUSH" -eq 1 ]] && { echo "BLOCKED: run ship-loop-gate before push"; exit 1; }
  fi
fi

if [[ -f "$CHANGELOG" && -f "$KG_DB" ]]; then
  if [[ "$CHANGELOG" -nt "$KG_DB" ]]; then
    warn "CHANGELOG newer than kg.db — run scripts/bin/enrichment-sync.sh"
    if [[ "$PRE_PUSH" -eq 1 ]]; then
      echo "BLOCKED: brain CHANGELOG ahead of kg.db — run: scripts/bin/enrichment-sync.sh" >&2
      exit 1
    fi
  else
    ok "kg.db covers CHANGELOG mtime"
  fi
fi

if ! python3 "$ROOT/scripts/lib/kg_watermark_gate.py" check --soft >/dev/null 2>&1; then
  warn "KG branch-set stale vs watermark — run: scripts/bin/kg-ensure-fresh.sh"
  if [[ "$PRE_PUSH" -eq 1 ]]; then
    echo "BLOCKED: KG watermark stale — run: scripts/bin/kg-switch.sh" >&2
    exit 1
  fi
else
  ok "KG branch-set fresh (watermark gate)"
fi

if [[ -f "$PENDING" && -f "$CHANGELOG" ]]; then
  cl_mtime=$(stat -c %Y "$CHANGELOG" 2>/dev/null || stat -f %m "$CHANGELOG")
  pend_mtime=$(stat -c %Y "$PENDING" 2>/dev/null || stat -f %m "$PENDING")
  if [[ "$cl_mtime" -lt "$pend_mtime" ]]; then
    _merge_exempt=0
    if python3 "$ROOT/scripts/lib/ship_push_gate.py" --is-merge-head 2>/dev/null; then
      _merge_exempt=1
      ok "merge commit — brain CHANGELOG not required"
    else
      warn "git commit at $(cat "$PENDING") but brain CHANGELOG not updated since — prepend via cursor-bundle/kg/bin/changelog-add.sh"
    fi
    if [[ "$PRE_PUSH" -eq 1 && "$_merge_exempt" -eq 0 ]]; then
      echo ""
      echo "BLOCKED: ship fix without brain changelog. Run:"
      echo "  cursor-bundle/kg/bin/changelog-add.sh \"## DATE | repo \\\`sha\\\` | ...\" \"detail with apiName request names\""
      exit 1
    fi
  else
    ok "CHANGELOG updated after last commit flag"
  fi
fi

# Last committed service repo (from post-commit hook) should appear in CHANGELOG
LAST="$ROOT/.cursor/.last-ship-commit"
if [[ -f "$CHANGELOG" && -f "$LAST" ]]; then
  repo=$(sed -n '1p' "$LAST")
  sha=$(sed -n '2p' "$LAST")
  if [[ -n "$repo" && -n "$sha" ]]; then
    if grep -q "$sha" "$CHANGELOG" 2>/dev/null; then
      ok "last ship $repo@$sha in CHANGELOG"
    else
      warn "last ship $repo@$sha not in CHANGELOG"
    fi
  fi
fi

# Money companion WARN: DeathForeclosure / DCF writer in recent kg-flow without registry/runbook markers
if [[ -f "$CHANGELOG" ]]; then
  if python3 "$ROOT/scripts/lib/registry_companion_gate.py" check; then
    ok "DCF companion markers (registry/runbook) when kg-flow is DCF/EXTRA"
  else
    warn "money companion incomplete for top DCF kg-flow — registry note + runbook A2/B required (feedback_post_ship_registry_runbook_gap_mandatory.md)"
    [[ "$PRE_PUSH" -eq 1 ]] && echo "WARN (non-blocking): companion knowledge lag — still pushable but DoD incomplete" >&2
  fi
fi

if [[ "$issues" -eq 0 ]]; then
  echo "=== enrichment audit: PASS ==="
else
  echo "=== enrichment audit: $issues issue(s) — see above ==="
fi

# --pre-push only hard-blocks: commit flag without changelog update (already exited 1 above)
exit 0
