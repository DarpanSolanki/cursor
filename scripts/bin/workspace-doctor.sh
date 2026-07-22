#!/usr/bin/env bash
# Unified workspace health — KG, hooks, DB, registry, optional services.
# Usage:
#   workspace-doctor.sh           # quick (default)
#   workspace-doctor.sh --full    # smoke-workspace (KG CLI + hooks offline)
#   workspace-doctor.sh --services # include DPIC service HTTP checks
#   workspace-doctor.sh --env-smoke # db ping per env-matrix → workspace-ops-state.md
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

MODE=quick
ENV_SMOKE=0
for arg in "$@"; do
  case "$arg" in
    --full) MODE=full ;;
    --services) MODE=services ;;
    --quick) MODE=quick ;;
    --env-smoke) ENV_SMOKE=1 ;;
    -h|--help)
      echo "Usage: workspace-doctor.sh [--quick|--full|--services|--env-smoke]"
      exit 0
      ;;
  esac
done

echo "=== workspace doctor ($MODE) ==="
fail=0
die() { echo "  FAIL $1"; fail=1; }
ok() { echo "  OK  $1"; }

echo ""
echo "--- repos (branch@sha) ---"
for d in "$ROOT"/novopay-* "$ROOT"/trustt-*; do
  [[ -d "$d/.git" ]] || continue
  printf "  %-40s %s @ %s\n" "$(basename "$d")" \
    "$(git -C "$d" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')" \
    "$(git -C "$d" rev-parse --short=10 HEAD 2>/dev/null || echo '?')"
done

echo ""
echo "--- registry ---"
if python3 scripts/testing/lib/validate_registry.py; then ok "registry.json"; else die "registry.json"; fi

echo ""
echo "--- git workspace (cross-session) ---"
if python3 scripts/bin/git_workspace.py status --write 2>/dev/null | head -8; then
  ok "git-workspace-state.json"
else
  die "git workspace status failed"
fi

echo ""
echo "--- KG freshness ---"
if bash scripts/bin/kg-ensure-fresh.sh --check-only --quiet 2>/dev/null; then
  ok "KG FRESH (branch-set)"
elif bash scripts/bin/kg-quick-check.sh --json 2>/dev/null | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('cache_hit'))" | grep -q True; then
  ok "KG stale but cache hit available — run: scripts/bin/kg-session-sync.sh (~1s)"
else
  die "KG stale — run: scripts/bin/kg-session-sync.sh"
  bash scripts/bin/kg-quick-check.sh 2>&1 | head -3 || true
fi
if [[ -f .cursor/workspace-kg-state.md ]]; then
  ok "workspace-kg-state.md"
else
  die "missing .cursor/workspace-kg-state.md"
fi

echo ""
if [[ "$MODE" == "full" ]]; then
  bash scripts/bin/smoke-workspace.sh || fail=1
else
  bash scripts/bin/setup-local.sh || fail=1
fi

if [[ "$MODE" == "services" || "$MODE" == "full" ]]; then
  echo ""
  echo "--- services (HTTP) ---"
  bash scripts/dpic/run_preflight.sh || fail=1
fi

echo ""
echo "--- hygiene ---"
if bash scripts/bin/workspace-hygiene.sh --verbose 2>/dev/null | tail -5; then
  ok "workspace hygiene"
fi

if [[ "$ENV_SMOKE" == 1 || "$MODE" == "full" ]]; then
  echo ""
  echo "--- env-smoke ---"
  if bash scripts/bin/env-smoke.sh --write-state; then
    ok "env-smoke → workspace-ops-state.md"
  else
    die "env-smoke"
  fi
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "=== DOCTOR: HEALTHY ==="
  echo "Next: make -C scripts test-smoke-quick  |  ntest auto <apiName>"
  exit 0
else
  echo "=== DOCTOR: ISSUES FOUND ==="
  exit 1
fi
