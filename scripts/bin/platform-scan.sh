#!/usr/bin/env bash
# Parallel platform scan — map + contracts + chains in one pass.
# Usage:
#   scripts/bin/platform-scan.sh              # parallel scan + enrich
#   scripts/bin/platform-scan.sh --with-kg    # + full KG rebuild
#   scripts/bin/platform-scan.sh --workers 6
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
exec python3 "$ROOT/scripts/testing/platform_scan.py" run "$@"
