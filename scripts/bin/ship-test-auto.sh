#!/usr/bin/env bash
# Auto-run ship tests for pending work (impact + deep). Agents/hooks only — not for users.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PENDING="$ROOT/.cursor/.pending-ship-work.json"

[[ -f "$PENDING" ]] || { echo "ship-test-auto: no pending ship work"; exit 0; }

TIER="$(python3 -c "import json; print(json.load(open('$PENDING')).get('tier','workspace'))" 2>/dev/null || echo workspace)"
[[ "$TIER" == "workspace" ]] && {
  echo "ship-test-auto: workspace tier — validate only"
  python3 "$ROOT/scripts/testing/ntest.py" validate
  exit 0
}

PHASES="${SHIP_TEST_PHASES:-impact,deep}"
echo "=== ship-test-auto (tier=$TIER phases=$PHASES) ==="
exec python3 "$ROOT/scripts/lib/ship_test_plan.py" --from-pending --run --phases "$PHASES"
