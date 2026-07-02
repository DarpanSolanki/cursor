#!/usr/bin/env bash
# Assert DPI accrual/billing GL chain: transaction_master + catalogue + billing partitions.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

LOAN_ACCOUNT_ID="${1:?loan_account_id}"
SLICE_END_DATE="${2:-}"
AS_OF_DATE="${3:-}"

fail() { echo "FAIL: $*" >&2; exit 1; }

read -r accrual_cat billing_cat acc_orphans acc_wrong bill_orphans bill_wrong bill_no_part slice_booked <<<"$(
  dpi_pg -v ON_ERROR_STOP=1 -t -A -F' ' \
    -v loan_account_id="$LOAN_ACCOUNT_ID" \
    -v slice_end_date="${SLICE_END_DATE}" \
    -v as_of_date="${AS_OF_DATE}" \
    -f "$ROOT/scripts/dpic/sql/helpers/verify_dpi_eod_txn_chain.sql" | tail -1
)"

echo "=== DPI EOD txn chain (loan=$LOAN_ACCOUNT_ID accrual_cat=$accrual_cat billing_cat=$billing_cat) ==="
echo "  accrual_orphans=$acc_orphans wrong_cat=$acc_wrong billing_orphans=$bill_orphans wrong_cat=$bill_wrong no_partition=$bill_no_part"

[[ "${acc_orphans:-0}" == "0" ]] || fail "accrual_posting_date set but txn missing (orphans=$acc_orphans)"
[[ "${acc_wrong:-0}" == "0" ]] || fail "accrual txn wrong catalogue (expected $accrual_cat, wrong=$acc_wrong)"
[[ "${bill_orphans:-0}" == "0" ]] || fail "billing_posting_date set but txn missing (orphans=$bill_orphans)"
[[ "${bill_wrong:-0}" == "0" ]] || fail "billing txn wrong catalogue (expected $billing_cat, wrong=$bill_wrong)"
[[ "${bill_no_part:-0}" == "0" ]] || fail "billing txn exists but transaction_partition_details empty (count=$bill_no_part)"

if [[ -n "$SLICE_END_DATE" ]]; then
  [[ "${slice_booked:-0}" -gt 0 ]] || fail "slice end_date=$SLICE_END_DATE not accrual-booked"
fi

echo "PASS: DPI EOD txn chain OK"
