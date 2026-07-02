#!/usr/bin/env bash
# Shared GL leg verification for DPI write-path harnesses.
# Source after dpi_demo_fixture.sh
set -euo pipefail

_DPI_GL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DPI_GL_ROOT="$(cd "$_DPI_GL_DIR/../../.." && pwd)"
DPI_GL_SQL="$DPI_GL_ROOT/scripts/dpic/sql/helpers"

# Resolve latest payment txn ref for loan_account_id.
dpi_resolve_latest_payment_txn() {
  local loan_account_id="$1"
  dpi_pg -v ON_ERROR_STOP=1 -t -A \
    -v loan_account_id="$loan_account_id" \
    -f "$DPI_GL_SQL/resolve_latest_payment_txn.sql" | head -1 | tr -d '[:space:]'
}

# Read leg_count and max_leg_amount for a posted txn (REAL mode).
# Usage: read -r cnt max <<< "$(dpi_read_gl_legs "$txn_ref" LOAN_PREPAYMENT 'BILLED_DPI_INT_AMT,ADV_BILLED_DPI_INT_AMT' "$stan")"
dpi_read_gl_legs() {
  local txn_ref="$1" catalogue_type="$2" reference_codes="$3" stan="${4:-}"
  dpi_pg -v ON_ERROR_STOP=1 -t -A \
    -v txn_reference="$txn_ref" \
    -v catalogue_type="$catalogue_type" \
    -v reference_codes="$reference_codes" \
    -v stan="$stan" \
    -f "$DPI_GL_SQL/verify_gl_legs.sql" | head -1 | tr '|' ' '
}

# Assert GL legs exist on latest payment txn for loan (foreclosure / repayment REAL posts).
dpi_assert_gl_legs_from_payment() {
  local loan_account_id="$1" catalogue_type="$2" reference_codes="$3" label="${4:-GL legs}"
  local stan="${5:-}" txn_ref leg_count max_amt min_legs="${6:-1}"

  txn_ref="$(dpi_resolve_latest_payment_txn "$loan_account_id")"
  if [[ -z "$txn_ref" ]]; then
    echo "FAIL: $label — no payment txn ref for loan_account_id=$loan_account_id" >&2
    return 1
  fi
  read -r leg_count max_amt <<<"$(dpi_read_gl_legs "$txn_ref" "$catalogue_type" "$reference_codes" "$stan")"
  if [[ "${leg_count:-0}" -lt "$min_legs" ]]; then
    echo "FAIL: $label — leg_count=$leg_count (txn=$txn_ref catalogue=$catalogue_type)" >&2
    return 1
  fi
  echo "OK: $label count=$leg_count max_amount=$max_amt txn=$txn_ref"
}

dpi_fixture_health_line() {
  local loan_account_id="${1:-${LOAN_ACCOUNT_ID:-8060160}}"
  dpi_pg -v ON_ERROR_STOP=1 -t -A \
    -v loan_account_id="$loan_account_id" \
    -f "$DPI_GL_SQL/dpi_fixture_health.sql" | head -1 | tr '|' ' '
}

dpi_print_fixture_health() {
  local loan_account_id="${1:-${LOAN_ACCOUNT_ID:-8060160}}"
  read -r loan_st acct_st dpi_open cat_link <<<"$(dpi_fixture_health_line "$loan_account_id")"
  echo "FIXTURE health loan=$loan_account_id status=$loan_st/$acct_st dpi_open=$dpi_open cat10_11=$cat_link"
}

# Idempotent seeds required for part-prep / NPA write paths on product 6367.
dpi_ensure_dpi_write_catalogues() {
  dpi_pg -v ON_ERROR_STOP=1 -f "$DPI_GL_ROOT/scripts/dpic/sql/helpers/seed_part_prepayment_dpi_catalogue_6367.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -f "$DPI_GL_ROOT/scripts/dpic/sql/helpers/seed_npa_dpi_catalogue_6367.sql" >/dev/null 2>&1 || true
}
