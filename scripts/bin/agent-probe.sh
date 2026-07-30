#!/usr/bin/env bash
# Agent probe entry — EVERY timed probe must go through with-budget (never bare sleep/hang).
# Usage: agent-probe.sh --budget N --label <name> -- <cmd> [args...]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/bin/with-budget.py" "$@"
