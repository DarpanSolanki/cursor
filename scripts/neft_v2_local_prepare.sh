#!/usr/bin/env bash
# NEFTv2 local prepare — seed Chameleon stubs + probe (simulator :8018, not real bank).
# Run before INDL NEFT disburse on trains with USE_NEFT_V1=false (e.g. mfi_integration_v3.4.2.4).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SIM="${SIMULATOR_BASE:-http://127.0.0.1:8018}"

echo "=== neft_v2_local_prepare — ensure simulators ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure simulators

echo "=== seed mfi_simulator NEFTv2 JSON stubs ==="
bash "$ROOT/scripts/bin/db-local-write.sh" --file "$ROOT/scripts/mfi_simulator_neft_v2_seed.sql"

probe() {
  local api="$1" body="$2"
  local code
  code=$(curl -s -o /tmp/neft_v2_probe.json -w "%{http_code}" \
    -X POST "$SIM/simulate/json/$api" \
    -H 'Content-Type: application/json' \
    -d "$body")
  echo "  [$code] $api"
  if [[ "$code" != "200" ]]; then
    echo "FAIL probe $api — body:" >&2
    head -c 400 /tmp/neft_v2_probe.json >&2 || true
    echo >&2
    return 1
  fi
}

echo "=== probe Chameleon NEFTv2 endpoints ==="
probe doGenericSyncSTPNEF '{"idtxn":"ST_NEF","GenericSyncSTPRequestDTO":{}}'
probe doGenericSyncSTPNEI '{"idtxn":"ST_NEI","GenericSyncSTPRequestDTO":{}}'
probe doGenericSyncSTPInquiry '{"GenericSyncSTPInquiryRequestDTO":{}}'
echo "=== neft_v2_local_prepare PASS ==="
