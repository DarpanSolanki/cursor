#!/usr/bin/env bash
# Scan cross-service contracts (orchestration XML + Kafka) and refresh contracts.jsonl
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/testing/contract_graph.py" "$@"
