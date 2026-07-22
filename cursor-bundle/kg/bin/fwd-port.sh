#!/usr/bin/env bash
# Compatibility wrapper — docs historically pointed at cursor-bundle/kg/bin/fwd-port.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
exec bash "$ROOT/scripts/bin/fwd-port.sh" "$@"
