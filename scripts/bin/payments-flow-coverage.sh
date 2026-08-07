#!/usr/bin/env bash
# Payments flow coverage report — ALL domains (read, write, batch, money).
# Usage: payments-flow-coverage.sh [--json] [--domain NAME]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python3 scripts/lib/payments_flow_domains.py "$@"
