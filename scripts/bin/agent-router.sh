#!/usr/bin/env bash
# Classify user task → skill chain + consultation order (proof-backed routing).
# Usage:
#   agent-router.sh classify "foreclosure batch expiry SDCP-10400"
#   agent-router.sh classify "run dpi sanity"
#   agent-router.sh list
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/agent_router.py" "$@"
