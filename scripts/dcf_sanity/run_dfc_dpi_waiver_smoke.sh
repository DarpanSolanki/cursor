#!/usr/bin/env bash
# Death FC + child foreclosure DPI waiver smoke (simulation + ICF + SQL legs).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
export LOAN_ACCOUNT_ID="${LOAN_ACCOUNT_ID:-8060160}"
export ACCOUNT_NUMBER="${ACCOUNT_NUMBER:-6004044425}"
export ICF_LAN="${ICF_LAN:-6004044425}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
export PGPASSWORD="${PGPASSWORD:-yugabyte}"

echo "=== Death FC / foreclosure DPI waiver smoke ==="
bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

# Prerequisite: DPI billed state on fixture LAN
if ! "${PG[@]}" -t -A -c \
  "SELECT COUNT(*) FROM mfi_accounting.loan_due_details ldd
   JOIN mfi_accounting.loan_account la ON la.id = ldd.loan_account_id
   WHERE la.account_number = '$ACCOUNT_NUMBER' AND ldd.component_type = 'DPI' AND ldd.is_deleted = false;" \
  | grep -qvE '^0$'; then
  echo ">>> DPI due missing — seeding via dpic.eod_dpi"
  JOB_TIME="${JOB_TIME:-1781699400000}" bash "$ROOT/scripts/dpic/run_eod_dpi_only.sh"
fi

bash "$ROOT/scripts/bin/ntest.sh" run dpic.foreclosure_sim
bash "$ROOT/scripts/bin/ntest.sh" run foreclosure.individual_child

"${PG[@]}" -v ON_ERROR_STOP=1 \
  -v lan="$ACCOUNT_NUMBER" \
  -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dcf_sanity/dcf_dpi_waiver_verify.sql"

echo "=== Death FC / foreclosure DPI waiver smoke PASS ==="
