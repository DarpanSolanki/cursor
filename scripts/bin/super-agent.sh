#!/usr/bin/env bash
# Super agent — unified KG + test KG + skills orchestrator.
# Usage:
#   super-agent.sh session
#   super-agent.sh orient disburseLoan
#   super-agent.sh sync [--kg]
#   super-agent.sh gaps --money
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/super_agent.py" "$@"
