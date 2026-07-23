#!/usr/bin/env bash
# Dynamic impact-tests — git diff → KG blast radius → registry cases + WHY.
# Usage:
#   bash scripts/bin/impact-tests.sh                  # banner from pending∪dirty
#   bash scripts/bin/impact-tests.sh --mark-ran       # record for ship gate
#   bash scripts/bin/impact-tests.sh --check-ran      # exit 1 if not run
#   bash scripts/bin/impact-tests.sh --path <rel> …
#   bash scripts/bin/impact-tests.sh --range origin/main...HEAD
#   IMPACT_TESTS_WAIVER="reason" bash scripts/bin/impact-tests.sh --waiver "$IMPACT_TESTS_WAIVER"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/impact_tests.py" "$@"
