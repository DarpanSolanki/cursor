#!/usr/bin/env bash
# Ship discipline — write or check machine gate for money/service ships.
# Usage:
#   ship-discipline.sh check
#   ship-discipline.sh write --minimal-fix "..." --read-path No --hot-path PASS \
#       --verify-mode RUNTIME_VERIFIED --kg CASES --assumptions-none
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/ship_discipline_gate.py" "$@"
