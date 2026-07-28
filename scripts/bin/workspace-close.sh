#!/usr/bin/env bash
# Single task-close entry: fresh KG → ship-loop → sync → knowledge gate → hygiene.
#
# Usage:
#   workspace-close.sh --from-pending
#   workspace-close.sh --from-pending --force   # re-run even if already satisfied
#   workspace-close.sh --api getLoanAccountOverviewDetails [--api ...]
#   workspace-close.sh --from-pending --capture   # capture-flow when CAPTURE_FTG set
#   workspace-close.sh --tests-only             # ship-loop --skip-gate, no close gate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
GATE="$ROOT/scripts/lib/ship_push_gate.py"
FROM_PENDING=0
TESTS_ONLY=0
CAPTURE=0
FORCE=0
FTG="${CAPTURE_FTG:-}"
APIS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-pending) FROM_PENDING=1; shift ;;
    --force) FORCE=1; shift ;;
    --api) APIS+=("$2"); shift 2 ;;
    --capture|--money) CAPTURE=1; shift ;;
    --tests-only) TESTS_ONLY=1; shift ;;
    -h|--help)
      sed -n '2,10p' "$0"
      exit 0
      ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done

die() { echo "workspace-close FAIL: $*" >&2; exit 1; }

echo "=== workspace-close ==="

PENDING="$ROOT/.cursor/.pending-ship-work.json"
PASSED="$ROOT/.cursor/.ship-loop-passed.json"
CHANGELOG="$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md"
PENDING_KG="$ROOT/.cursor/.pending-kg-rebuild"

_changelog_covers_pending_kg() {
  [[ ! -f "$PENDING_KG" ]] && return 0
  [[ ! -f "$CHANGELOG" ]] && return 1
  python3 - <<'PY' "$PENDING_KG" "$CHANGELOG"
import sys
from datetime import datetime, timezone
from pathlib import Path
pending_kg, changelog = Path(sys.argv[1]), Path(sys.argv[2])
pend_iso = pending_kg.read_text(encoding="utf-8").strip()
try:
    pend = datetime.strptime(pend_iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
except Exception:
    raise SystemExit(1)
cl_mtime = changelog.stat().st_mtime
raise SystemExit(0 if cl_mtime >= pend.timestamp() - 2 else 1)
PY
}

# 0 — skip when pending work already closed (fingerprints + tier; not wall-clock alone)
if [[ "$FROM_PENDING" -eq 1 && "$FORCE" -eq 0 && "$TESTS_ONLY" -eq 0 ]]; then
  if [[ -f "$PENDING" ]] && python3 "$GATE" --satisfied 2>/dev/null; then
    passed_at="$(python3 -c "import json; print(json.load(open('$PASSED')).get('passed_at','?'))" 2>/dev/null || echo '?')"
    echo "SKIP: ship loop already satisfied (passed_at=$passed_at) — use --force to re-run"
    profile="$(python3 "$GATE" --close-profile 2>/dev/null || echo minimal)"
    if [[ "$profile" != "minimal" ]] || [[ -f "$PENDING_KG" ]]; then
      bash "$ROOT/scripts/bin/ship-knowledge-gate.sh" --profile "$profile" || die "ship-knowledge-gate failed"
    else
      bash "$ROOT/scripts/bin/workspace-hygiene.sh" --gate 2>/dev/null \
        || bash "$ROOT/scripts/bin/workspace-hygiene.sh" --clean 2>/dev/null || true
    fi
    rm -f "$ROOT/.cursor/.pending-ship-nudge" "$PENDING" 2>/dev/null || true
    echo "=== workspace-close: PASS (cached) ==="
    exit 0
  fi
  if [[ ! -f "$PENDING" ]]; then
    echo "SKIP: no pending ship work"
    echo "=== workspace-close: PASS (nothing pending) ==="
    exit 0
  fi
fi

CLOSE_TIER="$(python3 "$GATE" --pending-tier 2>/dev/null || echo workspace)"
CLOSE_PROFILE="$(python3 "$GATE" --close-profile 2>/dev/null || echo minimal)"

# 1 — KG integrity + freshness (no stale knowledge)
if ! python3 "$ROOT/cursor-bundle/kg/bin/kg.py" validate >/dev/null 2>&1; then
  die "kg validate failed — run: scripts/bin/kg-switch.sh"
fi
if ! bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet 2>/dev/null; then
  echo "→ KG stale — syncing branch-set cache"
  bash "$ROOT/scripts/bin/kg-switch.sh" --quiet 2>/dev/null || bash "$ROOT/scripts/bin/kg-session-sync.sh" --quiet || die "KG sync failed"
  bash "$ROOT/scripts/bin/kg-ensure-fresh.sh" --quiet || die "KG still STALE after sync"
fi
echo "OK: KG validate + FRESH"
export WORKSPACE_CLOSE_KG_DONE=1

python3 "$ROOT/scripts/lib/kg_watermark_gate.py" check --block-verified \
  || die "KG watermark stale — run: scripts/bin/kg-switch.sh"

# 1b — registry companion + ntest schema when pending ship work exists
if [[ -f "$PENDING" ]]; then
  echo "→ ntest validate (pending ship)"
  python3 "$ROOT/scripts/testing/ntest.py" validate || die "registry.json validate failed"
  python3 "$ROOT/scripts/lib/registry_companion_gate.py" check --hard \
    || die "registry/runbook companion stale — update suite note/runbook to match code"
fi

# 2 — brain changelog if commit pending (merge/sync commits exempt)
if [[ -f "$PENDING_KG" && -f "$CHANGELOG" ]]; then
  if _changelog_covers_pending_kg; then
    echo "OK: brain CHANGELOG covers last commit"
  else
    if [[ "${SHIP_CLOSE_ALLOW_MERGE:-}" == "1" ]] \
        || python3 "$GATE" --is-merge-head 2>/dev/null; then
      echo "OK: merge/sync commit — brain CHANGELOG gate skipped"
      rm -f "$PENDING_KG" 2>/dev/null || true
    else
      die "brain CHANGELOG not updated after commit — run: cursor-bundle/kg/bin/changelog-add.sh --kg-flow"
    fi
  fi
elif [[ -f "$PENDING_KG" ]]; then
  echo "WARN: pending-kg-rebuild but no CHANGELOG file"
fi

# 2b — stack preflight (Phase D)
if [[ -f "$PENDING" ]]; then
  echo "→ stack-doctor (workspace-close preflight)"
  bash "$ROOT/scripts/bin/stack-doctor.sh" --remediate || die "stack-doctor failed — fix stack before ship-loop"
fi

# 2c — impact-tests gate READ-ONLY (never write records — ship-loop writes after tests)
CLOSE_TIER_CHECK="$(python3 -c "
import json
from pathlib import Path
p=Path('$PENDING')
print(json.load(open(p)).get('tier','workspace') if p.is_file() else 'workspace')
" 2>/dev/null || echo workspace)"
if [[ "$CLOSE_TIER_CHECK" == "money" || "$CLOSE_TIER_CHECK" == "service" ]]; then
  echo "→ impact-tests gate check (read-only)"
  python3 "$ROOT/scripts/lib/impact_tests.py" --banner 2>/dev/null | head -20 || true
  if python3 "$ROOT/scripts/lib/impact_tests.py" --check-ran >/dev/null 2>&1; then
    echo "→ impact-tests record: $(python3 "$ROOT/scripts/lib/impact_tests.py" --check-ran 2>/dev/null || true)"
  else
    echo "→ impact-tests: no matching HEAD record yet (ship-loop will write after tests)"
  fi
fi

# 3 — tier-aware ship-loop (workspace | service | money); knowledge gate once at end
SHIP_ARGS=()
[[ "$FROM_PENDING" -eq 1 ]] && SHIP_ARGS+=(--from-pending)
[[ "$TESTS_ONLY" -eq 1 ]] && SHIP_ARGS+=(--skip-gate)
export SHIP_LOOP_SKIP_KNOWLEDGE_GATE=1
for a in "${APIS[@]}"; do SHIP_ARGS+=(--api "$a"); done
bash "$ROOT/scripts/bin/ship-loop-gate.sh" "${SHIP_ARGS[@]}" || die "ship-loop-gate failed"

# 4 — optional capture-flow (money proof)
if [[ "$CAPTURE" -eq 1 && -n "$FTG" && -x "$ROOT/scripts/bin/capture-flow.sh" ]]; then
  echo "→ capture-flow --ftg $FTG"
  bash "$ROOT/scripts/bin/capture-flow.sh" --ftg "$FTG" || die "capture-flow failed"
fi

[[ "$TESTS_ONLY" -eq 1 ]] && { echo "=== workspace-close: tests-only PASS ==="; exit 0; }

# 5 — intel sync (workspace tier: skip unless many stale layers)
STALE_N=0
if [[ -f "$ROOT/scripts/testing/sync_engine.py" ]]; then
  STALE_N=$(python3 "$ROOT/scripts/testing/sync_engine.py" status 2>/dev/null | grep -c STALE || true)
fi
if [[ "$CLOSE_TIER" == "workspace" && "${STALE_N:-0}" -le 2 ]]; then
  echo "→ super-agent sync skipped (workspace tier, stale_layers=${STALE_N:-0})"
elif [[ "${STALE_N:-0}" -gt 2 ]]; then
  echo "→ super-agent sync --full ($STALE_N stale layers)"
  bash "$ROOT/scripts/bin/super-agent.sh" sync --full || true
else
  echo "→ super-agent sync"
  bash "$ROOT/scripts/bin/super-agent.sh" sync || true
fi

# 6 — enrichment cases if changelog ahead of kg.db (money/service only — workspace kb edits skip)
if [[ "$CLOSE_PROFILE" != "minimal" && -f "$CHANGELOG" && -f "$ROOT/cursor-bundle/kg/data/kg.db" ]]; then
  if [[ "$CHANGELOG" -nt "$ROOT/cursor-bundle/kg/data/kg.db" ]]; then
    echo "→ kg-enrich --cases"
    bash "$ROOT/scripts/bin/kg-enrich.sh" --cases 2>/dev/null || true
  fi
fi

# 7 — knowledge gate + hygiene (single pass; tier profile)
bash "$ROOT/scripts/bin/ship-knowledge-gate.sh" --profile "$CLOSE_PROFILE" || die "ship-knowledge-gate failed"

# 8 — hub refresh (service/money only — workspace SQL/scripts don't need hub rewrite)
if [[ "$CLOSE_PROFILE" != "minimal" && -x "$ROOT/scripts/bin/write-intelligence-hub.sh" ]]; then
  bash "$ROOT/scripts/bin/write-intelligence-hub.sh" >/dev/null 2>&1 || true
fi

# 9 — clear pending flags on full pass
rm -f "$ROOT/.cursor/.pending-ship-nudge" "$PENDING" 2>/dev/null || true
if [[ -f "$PENDING_KG" && -f "$CHANGELOG" ]]; then
  if _changelog_covers_pending_kg; then
    rm -f "$PENDING_KG" 2>/dev/null || true
  fi
fi

echo "=== workspace-close: PASS ==="
