#!/usr/bin/env bash
# Unified local disburseLoan entry — PRODUCT_TYPE=INDL|JLG|SHG (default JLG).
# Value-level column audits run inside disburse_loan_sanity.py (fail-closed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PRODUCT_TYPE="$(echo "${PRODUCT_TYPE:-JLG}" | tr '[:lower:]' '[:upper:]')"
STAGE_SUITE="${STAGE_SUITE:-minimal}"

case "$PRODUCT_TYPE" in
  JLG)
    exec bash "$ROOT/scripts/bin/disburse-quick.sh" "$@"
    ;;
  SHG)
    exec bash "$ROOT/scripts/bin/disburse-shg-quick.sh" "$@"
    ;;
  INDL|INDIVIDUAL)
    exec bash "$ROOT/scripts/bin/disburse-indl-quick.sh" "$@"
    ;;
  *)
    echo "Unknown PRODUCT_TYPE=$PRODUCT_TYPE (use INDL|JLG|SHG)" >&2
    exit 2
    ;;
esac
