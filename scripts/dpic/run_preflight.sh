#!/usr/bin/env bash
# Quick DPIC environment check (DB + services + product 6367 EMI config).
set -euo pipefail
# shellcheck disable=SC1091
source "$(cd "$(dirname "$0")" && pwd)/lib/preflight.sh"
dpic_run_preflight
dpic_print_next_steps
