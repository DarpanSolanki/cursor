#!/usr/bin/env bash
# Regenerate session intelligence hub (--fast skips slow kg subprocess).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FAST=0
for a in "$@"; do
  case "$a" in
    --fast|-f) FAST=1 ;;
  esac
done
args=(--write)
[[ "$FAST" == 1 ]] && args+=(--fast)
exec python3 "$ROOT/scripts/testing/intelligence_hub.py" "${args[@]}"
