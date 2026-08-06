#!/usr/bin/env bash
# Tiered KG enrich — see scripts/bin/enrichment-sync.sh and 20-ship-gates.md.
#   kg-enrich.sh           — auto tier (cases vs full)
#   kg-enrich.sh --cases   — CHANGELOG / case precedents only
#   kg-enrich.sh --force   — full graph rebuild
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MODE=auto
for a in "$@"; do
  case "$a" in
    --cases|--cases-only) MODE=cases ;;
    --force) MODE=full ;;
  esac
done

echo "=== KG enrich (mode=$MODE) ==="
case "$MODE" in
  cases)
    python3 cursor-bundle/kg/bin/refresh_cases.py
    ;;
  full)
    bash cursor-bundle/kg/bin/build.sh --force
    ;;
  auto)
    bash scripts/bin/enrichment-sync.sh
    ;;
esac
echo ""
python3 cursor-bundle/kg/bin/kg.py fresh
python3 cursor-bundle/kg/bin/kg_session.py stamp >/dev/null 2>&1 || true
python3 cursor-bundle/kg/bin/kg.py watermark --no-drift-check | head -12
rm -f "$ROOT/.cursor/.pending-kg-rebuild" 2>/dev/null || true
echo ""
echo "Cases sample: python3 cursor-bundle/kg/bin/kg.py cases disburseLoan | head -5"
