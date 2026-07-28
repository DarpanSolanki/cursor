#!/usr/bin/env bash
# Dynamic impact-tests — git diff → KG blast radius → registry cases + WHY.
# Usage:
#   bash scripts/bin/impact-tests.sh                  # banner from pending shipped code
#   bash scripts/bin/impact-tests.sh --mark-ran       # record after tests (HEAD sha keyed)
#   bash scripts/bin/impact-tests.sh --check-ran      # exit 1 if HEAD sha mismatch
#   bash scripts/bin/impact-tests.sh --path <rel> …
#   bash scripts/bin/impact-tests.sh --range origin/main...HEAD
# Human waiver only: bash scripts/bin/impact-tests.sh --human-waiver "reason"
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/impact_tests.py" "$@"
