#!/usr/bin/env bash
# Drop clean+pushed zombie paths from .pending-ship-work.json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/pending_ship_gc.py" "$@"
