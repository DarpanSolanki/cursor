#!/usr/bin/env bash
# Compatibility entry — prefer workspace-verify / workspace-doctor.
# Usage: workspace-bootstrap.sh [--repair]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
if [[ "${1:-}" == "--repair" ]]; then
  exec bash "$ROOT/scripts/bin/workspace-verify.sh" --repair
fi
exec bash "$ROOT/scripts/bin/workspace-doctor.sh" "$@"
