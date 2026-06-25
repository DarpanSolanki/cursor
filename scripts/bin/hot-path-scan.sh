#!/usr/bin/env bash
# Workspace hot-path perf heuristic (DAO-in-loop, stream-in-loop). Agents only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/hot_path_scan.py" "$@"
