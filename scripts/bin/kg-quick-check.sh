#!/usr/bin/env bash
# Cheap branch-set check — no sync. Exit 0=fresh, 1=stale/missing.
#
# Usage:
#   kg-quick-check.sh           # check only
#   kg-quick-check.sh --json    # machine-readable (kg_session.py decide)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
BIN="$ROOT/cursor-bundle/kg/bin"

if [[ "${1:-}" == "--json" ]]; then
  exec python3 "$BIN/kg_session.py" decide
fi

_decision="$(python3 "$BIN/kg_session.py" decide --fast 2>/dev/null || echo '{}')"
_fresh="$(python3 -c "import json,sys; d=json.loads(sys.argv[1]); print('yes' if d.get('fresh') and d.get('tier')=='skip' else 'no')" "$_decision")"
_key="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('key','?')[:12])" "$_decision")"

if [[ "$_fresh" == "yes" ]]; then
  echo "KG quick-check: FRESH (branch-set $_key…)"
  exit 0
fi
_tier="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('tier','?'))" "$_decision")"
_reason="$(python3 -c "import json,sys; print(json.loads(sys.argv[1]).get('reason',''))" "$_decision")"
_cache="$(python3 -c "import json,sys; print('yes' if json.loads(sys.argv[1]).get('cache_hit') else 'no')" "$_decision")"
echo "KG quick-check: NEEDS_SYNC tier=$_tier cache=$_cache — $_reason"
echo "Run: scripts/bin/kg-session-sync.sh  (cache restore ~1s when branch-set seen before)"
exit 1
