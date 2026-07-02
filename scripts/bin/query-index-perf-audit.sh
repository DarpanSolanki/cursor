#!/usr/bin/env bash
# Index + EXPLAIN audit for native @Query / batch reader SQL profiles.
#
# Usage:
#   query-index-perf-audit.sh --group dcf_insurance_reupload --db qa4
#   query-index-perf-audit.sh --group dcf_insurance_reupload --db local --json
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
exec python3 "$ROOT/scripts/lib/query_index_perf_audit.py" "$@"
