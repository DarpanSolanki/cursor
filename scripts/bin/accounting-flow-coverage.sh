#!/usr/bin/env bash
# Accounting flow coverage report — ALL domains (read, write, batch, money).
# Usage: accounting-flow-coverage.sh [--json] [--domain NAME]
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
python3 scripts/lib/accounting_flow_domains.py "$@"
