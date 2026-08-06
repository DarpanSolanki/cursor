#!/usr/bin/env bash
# One-time / periodic local workspace check for sliProd.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=== sliProd local setup check ==="

fail=0
check() { if "$@"; then echo "  OK: $*"; else echo "  FAIL: $*"; fail=1; fi; }

check test -f cursor-bundle/kg/data/kg.db
check test -f cursor-bundle/memory/MEMORY.md
check test -f cursor-bundle/brain/runbooks/pinpoint-rca-playbook.md
check test -x scripts/db-local.sh
check command -v python3 >/dev/null
check command -v psql >/dev/null
check pg_isready -h localhost -p 5433

echo ""
echo "=== Registry ==="
python3 scripts/testing/lib/validate_registry.py

echo ""
echo "=== KG smoke ==="
python3 cursor-bundle/kg/bin/kg.py validate
if ! bash scripts/bin/kg-ensure-fresh.sh --quiet 2>/dev/null; then
  echo "  WARN: KG was stale — ensure-fresh attempted sync"
fi
python3 cursor-bundle/kg/bin/kg.py fresh
python3 cursor-bundle/kg/bin/kg.py audit | head -25
python3 cursor-bundle/kg/bin/kg.py stale
python3 cursor-bundle/kg/bin/kg.py stats | head -3
python3 cursor-bundle/kg/bin/kg.py flow disburseLoan | head -3
if [[ -x .cursor/hooks/kg-session-watermark.sh ]]; then
  CLAUDE_PROJECT_DIR="$ROOT" .cursor/hooks/kg-session-watermark.sh >/dev/null 2>&1 || true
  check test -f .cursor/workspace-kg-state.md
fi

echo ""
echo "=== Local DB smoke ==="
scripts/db-local.sh --sql "SELECT 1 AS ok"

echo ""
echo "=== DPIC preflight (optional) ==="
if [[ -f scripts/dpic/run_preflight.sh ]]; then
  DPIC_SKIP_SERVICES=1 bash scripts/dpic/run_preflight.sh 2>/dev/null | head -12 || echo "  (DPIC preflight skipped — run: bash scripts/dpic/run_preflight.sh)"
fi

echo ""
if [[ "$fail" -eq 0 ]]; then
  echo "All checks passed."
else
  echo "Some checks failed — see above."
  exit 1
fi
