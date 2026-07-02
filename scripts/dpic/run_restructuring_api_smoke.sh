#!/usr/bin/env bash
# DPI restructuring API smoke — fields webapp will consume (overview + BPI + Loan 360).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
NTEST="$ROOT/scripts/bin/ntest.sh"

echo "=== DPI restructuring API smoke ==="
for case_id in dpic.overview_api dpic.restructuring_bpi_api dpic.summary_api; do
  echo ">>> ntest run $case_id"
  "$NTEST" run "$case_id"
done
echo "=== DPI restructuring API smoke PASS ==="
