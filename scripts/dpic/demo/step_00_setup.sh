#!/usr/bin/env bash
# Step 0 — One-time DB prep (product 6367 DPI rules + links).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/common.sh"

demo_banner "STEP 0 — Local DB setup (product ${DEMO_PRODUCT_ID}, DPI applicable)"
bash "$ROOT/scripts/dpic/run_setup.sh"
demo_talking_points \
  "Product scheme has DPI Applicable = Yes (monthly)." \
  "DPI GL accounting rules seeded from product doc."
demo_pause
