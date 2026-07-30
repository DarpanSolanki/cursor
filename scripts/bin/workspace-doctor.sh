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
echo "--- KG map-completeness ---"
if python3 "$ROOT/cursor-bundle/kg/bin/map_completeness.py" --doctor-warn 2>&1; then
  ok "map-completeness (no regression)"
else
  echo "  WARN map-completeness regression (see above) — not a hard fail"
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

echo ""
echo "--- KG telemetry ---"
_kg_doc="$(PYTHONPATH=scripts/lib python3 scripts/lib/kg_state_banner.py --doctor 2>&1 || true)"
if echo "$_kg_doc" | grep -q '^FAIL '; then
  while IFS= read -r _fl; do
    [[ "$_fl" == FAIL* ]] && die "${_fl#FAIL }"
  done <<<"$_kg_doc"
elif echo "$_kg_doc" | grep -q '^WARN '; then
  while IFS= read -r _fl; do
    [[ "$_fl" == WARN* ]] && echo "  WARN ${_fl#WARN }"
  done <<<"$_kg_doc"
  ok "KG telemetry (warns only)"
else
  ok "KG telemetry (no consecutive-miss / slow-build flags)"
fi

echo ""
echo "--- MCP tools (code SoT vs expected 19) ---"
_mcp_n="$(python3 - <<'PY'
import importlib.util
from pathlib import Path
p = Path("cursor-bundle/kg/mcp/kg_mcp_server.py")
spec = importlib.util.spec_from_file_location("kg_mcp_server", p)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(len(m.TOOLS))
PY
)"
if [[ "$_mcp_n" == "19" ]]; then
  ok "MCP TOOLS len=${_mcp_n} (expected 19; Cursor IDE may lag until MCP restart)"
else
  die "MCP TOOLS len=${_mcp_n} != 19 — registration drift vs kg-mcp-smoke"
fi

echo ""
echo "--- ntest flaky ---"
_flaky="$(PYTHONPATH=scripts/testing python3 -c "from ntest_telemetry import doctor_report; print(doctor_report())" 2>/dev/null || echo none)"
if [[ "$_flaky" == "none flaky" || "$_flaky" == "none" ]]; then
  ok "ntest telemetry: none flaky"
else
  echo "  WARN $_flaky"
  ok "ntest telemetry (flaky flagged — money never auto-skipped)"
fi

echo ""
echo "--- flow_coverage YES↔registry ---"
if python3 scripts/lib/flow_coverage_gate.py --warn 2>&1; then
  ok "flow_coverage YES rows have registry expect PASS/PARTIAL"
else
  echo "  WARN flow_coverage aspirational YES (see above) — flip only after green fresh run"
  ok "flow_coverage gate (WARN)"
fi

echo ""
echo "--- fixed tax (alwaysApply soft ceiling 35000B) ---"
_tax="$(python3 - <<'PY'
from pathlib import Path
root = Path(".cursor/rules")
aa = 0
off = []
for p in root.glob("*.mdc"):
    t = p.read_text(encoding="utf-8", errors="ignore")
    if "alwaysApply: true" not in t[:400]:
        continue
    b = len(t.encode("utf-8"))
    aa += b
    off.append((b, p.name))
off.sort(reverse=True)
print(f"BYTES {aa}")
print("TOP " + ", ".join(f"{n}={b}" for b, n in off[:5]))
print("WARN" if aa > 35000 else "OK")
PY
)"
_tax_bytes="$(echo "$_tax" | awk '/^BYTES/{print $2}')"
_tax_top="$(echo "$_tax" | awk '/^TOP/{sub(/^TOP /,""); print}')"
_tax_st="$(echo "$_tax" | awk '/^(WARN|OK)$/{print}')"
if [[ "$_tax_st" == "WARN" ]]; then
  echo "  WARN fixed tax ${_tax_bytes}B > 35000 soft ceiling — offenders: ${_tax_top}"
  ok "fixed tax (WARN — system watching weight)"
else
  ok "fixed tax ${_tax_bytes}B ≤ 35000 (top: ${_tax_top})"
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
echo "--- GAP-G / sync rails ---"
# freshness fail-closed already covered above
if [[ -f scripts/lib/loan_taxonomy.py && -f cursor-bundle/kg/curated/loan_taxonomy.json ]]; then
  ok "LAN taxonomy file + helper"
else
  die "LAN taxonomy missing"
fi
if python3 -c "from pathlib import Path; import ast; t=Path('scripts/lib/ship_discipline_gate.py').read_text(); assert 'fix_plan' in t" 2>/dev/null; then
  ok "FIX-PLAN gate present in ship_discipline_gate"
else
  die "FIX-PLAN gate missing"
fi
if python3 -c "from pathlib import Path; t=Path('scripts/lib/impact_tests.py').read_text(); assert '_apply_selection_tiering' in t and '_apply_representative_variants' in t" 2>/dev/null; then
  ok "selection tiering + representative variants"
else
  die "selection tiering missing"
fi
if python3 -c "from pathlib import Path; t=Path('scripts/testing/flowtest/invariants.py').read_text(); assert 'run_universal_invariants' in t" 2>/dev/null; then
  ok "universal invariants module"
else
  die "invariants module missing"
fi
if [[ -f .cursor/kg-grep-leak.jsonl ]] || [[ -f .cursor/hooks/kg-grep-leak-log.sh ]]; then
  ok "grep-leak counter hook (shell rg only — IDE Grep not hookable)"
else
  echo "  WARN grep-leak counter absent"
  ok "grep-leak (WARN)"
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
