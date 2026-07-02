#!/usr/bin/env bash
# Unified QA verify — schema contract + full pipeline + posting checklist + amount parity.
# Usage: run_dpi_qa_verify.sh <loan_account_id> <business_date_yyyy-mm-dd>
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${1:?loan_account_id}"
BUSINESS_DATE="${2:?business_date YYYY-MM-DD}"
SQL="$ROOT/scripts/dpic/sql/helpers"

fail() { echo "QA_VERIFY_FAIL: $*" >&2; exit 1; }

read -r sviol sdetail <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$BUSINESS_DATE" \
    -f "$SQL/verify_dpi_schema_contract.sql" | head -1
)"
[[ "${sviol:-1}" == "0" ]] || fail "schema contract violations=$sviol detail=${sdetail:-?}"

read -r pviol pdetail <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$BUSINESS_DATE" \
    -f "$SQL/verify_dpi_full_pipeline.sql" | head -1
)"
[[ "${pviol:-1}" == "0" ]] || fail "full pipeline violations=$pviol detail=${pdetail:-?}"

read -r mep eep bun bpp tps tbs accrued posted billed dpi_due parity <<<"$(
  dpi_pg -t -A -F' ' -v ON_ERROR_STOP=1 \
    -v loan_account_id="$LOAN_ACCOUNT_ID" -v business_date="$BUSINESS_DATE" \
    -f "$SQL/verify_dpi_qa_posting_checklist.sql" | head -1
)"
[[ "${bun:-1}" == "0" ]] || fail "QA checklist: boundary_unposted=$bun month_end_posted=$mep emi_due_posted=$eep"
[[ "${parity:-f}" == "t" ]] || fail "QA checklist: billing parity failed accrued=$accrued posted=$posted billed=$billed dpi_due=$dpi_due"

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$SQL/verify_dpi_amount_parity.sql" >/dev/null

echo "QA_VERIFY_OK loan=$LOAN_ACCOUNT_ID biz=$BUSINESS_DATE month_end_posted=$mep emi_due_posted=$eep billing_full=$parity"
