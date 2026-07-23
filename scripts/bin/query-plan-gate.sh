#!/usr/bin/env bash
# Query plan gate — DETECT query_touched → EXPLAIN local YB → PASS/WARN/FAIL.
# Usage:
#   query-plan-gate.sh --from-pending
#   query-plan-gate.sh --paths trustt-platform-accounting/.../FooRepository.java
#   query-plan-gate.sh --sql 'SELECT ...' [--label proof1]
#   query-plan-gate.sh --check-touched
#   query-plan-gate.sh --qa 4 --sql 'SELECT ...'   # SELECT EXPLAIN on QA (read-only)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export PYTHONPATH="$ROOT/scripts/lib${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$ROOT/scripts/lib/query_plan_gate.py" "$@"
