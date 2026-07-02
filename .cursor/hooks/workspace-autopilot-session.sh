#!/usr/bin/env bash
# sessionStart — autopilot health probe (fast; KG handled by kg-session-start).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
mkdir -p "$ROOT/scripts/scratch/logs"
timeout 15 bash "$ROOT/scripts/bin/workspace-autopilot.sh" session \
  >>"$ROOT/scripts/scratch/logs/workspace-autopilot-session.log" 2>&1 || true
echo '{}'
