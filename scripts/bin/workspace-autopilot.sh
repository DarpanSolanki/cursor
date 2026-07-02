#!/usr/bin/env bash
# Workspace autopilot — zero manual ops for agents.
#
#   workspace-autopilot.sh task "<user message>"   # classify + auto preflight
#   workspace-autopilot.sh session                 # hook: light health probe
#   workspace-autopilot.sh end                     # hygiene + auto-close pending
#   workspace-autopilot.sh plan "<message>" --json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/workspace_autopilot.py" "$@"
