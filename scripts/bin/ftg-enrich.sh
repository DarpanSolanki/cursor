#!/usr/bin/env bash
# Merge sources.jsonl + ntest registry + unit test scan into flows.jsonl
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/ftg.py" enrich "$@"
