#!/usr/bin/env bash
# DPI money-path SQL proof chain — run after EOD or before declaring DPI ship done.
# Usage: LOAN_ACCOUNT_ID=8060160 JOB_TIME=... bash scripts/bin/dpi-money-proof.sh [--posting] [--full]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
WITH_POSTING=0
FULL=0

for arg in "$@"; do
  case "$arg" in
    --posting) WITH_POSTING=1 ;;
    --full) FULL=1; WITH_POSTING=1 ;;
    -h|--help)
      sed -n '2,5p' "$0"
      exit 0
      ;;
  esac
done

echo "=== dpi-money-proof (loan=$LOAN_ACCOUNT_ID) ==="

bash "$ROOT/scripts/bin/dpi-booking-posting-guard.sh"

if [[ "$WITH_POSTING" -eq 1 ]]; then
  GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2026}" \
  GO_LIVE_ISO="${GO_LIVE_ISO:-2026-04-15}" \
  END_DATE="${END_DATE:-2026-06-01}" \
    bash "$ROOT/scripts/dpic/run_dpi_posting_calendar_regression.sh"
fi

bash "$ROOT/scripts/dpic/run_dpi_post_eod_verify.sh"

if [[ "$FULL" -eq 1 ]]; then
  bash "$ROOT/scripts/dpic/run_dpi_cross_eod_replay_guard.sh"
fi

echo "=== dpi-money-proof PASS ==="
