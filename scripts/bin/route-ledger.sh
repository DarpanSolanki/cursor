#!/usr/bin/env bash
# Route ledger — where the current task is, and whether it reached its terminal state.
#
#   route-ledger.sh resume                     # what is done / remaining / unmet (cheap)
#   route-ledger.sh terminal                   # verify goal predicates
#   route-ledger.sh close --declared evidence_cited,knowledge_loops --evidence-tier RUNTIME_VERIFIED
#   route-ledger.sh learn                      # router tuning report (report-only)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT/scripts/lib:$ROOT/scripts/testing:${PYTHONPATH:-}"
if [ "${1:-}" = "learn" ]; then
  shift
  exec python3 "$ROOT/scripts/lib/route_learn.py" report "$@"
fi
exec python3 "$ROOT/scripts/lib/route_ledger.py" "$@"
