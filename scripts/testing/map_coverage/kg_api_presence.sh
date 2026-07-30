#!/usr/bin/env bash
# Workspace KG presence check for domain api_hints that lack a money e2e yet.
# Asserts: request node exists in KG (kg search/flow). Used by map_coverage.* registry cases.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
API="${1:-${API_NAME:-}}"
if [[ -z "$API" ]]; then
  echo "Usage: $0 <apiName>"
  exit 2
fi
export KG_NO_AUTO_REBUILD=1
OUT=$(python3 "$ROOT/cursor-bundle/kg/bin/kg.py" search "$API" 2>/dev/null || true)
if ! echo "$OUT" | grep -Eq "request:.*${API}|request[[:space:]]+request:.*${API}|${API}"; then
  # fallback: flow must resolve
  FLOW=$(python3 "$ROOT/cursor-bundle/kg/bin/kg.py" flow "$API" 2>/dev/null || true)
  if ! echo "$FLOW" | grep -Eq "FLOW request:|processors"; then
    echo "FAIL: KG has no request/flow for api=$API"
    echo "$OUT" | head -20
    exit 1
  fi
fi
echo "PASS: KG map coverage for api=$API"
exit 0
