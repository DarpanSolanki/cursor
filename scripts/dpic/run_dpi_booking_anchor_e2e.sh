#!/usr/bin/env bash
# Booking-anchor / next-due seal proof (77921d275f class).
# Prior-EMI slice ending on next EMI INT/PRIN due must post (not this-installment INT only).
# Uses grace-chain fixture + milestone hops through EMI2 due; column audit must be 0.
#
# Usage:
#   bash scripts/dpic/run_dpi_booking_anchor_e2e.sh
#   LOAN_ACCOUNT_ID=8057160 END_DATE=2026-06-15 bash scripts/dpic/run_dpi_booking_anchor_e2e.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_fixture_constants.sh"
if [[ "${DPI_USE_CUSTOM_LOAN:-0}" != "1" ]]; then
  dpi_use_grace_chain_loan
fi
# shellcheck disable=SC1091
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh"

GO_LIVE_DDMM="${GO_LIVE_DDMM:-15-04-2025}"
GO_LIVE_ISO="${GO_LIVE_ISO:-2026-05-01}"
# EMI2 due on grace-chain is 2026-06-14 — run through that seal day
END_DATE="${END_DATE:-2026-06-15}"
GRACE_DAYS="${GRACE_DAYS:-3}"

fail() { echo "FAIL: $*" >&2; exit 1; }

echo "=== DPI booking-anchor / next-due seal E2E ==="
echo "    loan=$LOAN_ACCOUNT_ID LAN=$ACCOUNT_NUMBER end=$END_DATE"

bash "$ROOT/scripts/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/reset_dpi_booking_replay.sql" >/dev/null

dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" -v grace_days="$GRACE_DAYS" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/setup_multi_emi_dpi_e2e.sql" >/dev/null
dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" \
  -f "$ROOT/scripts/dpic/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null

read -r product_code <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
SELECT COALESCE(p.code, '7676')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
)"
dpi_set_go_live_and_refresh "$GO_LIVE_DDMM" "$product_code"

export ROOT LOAN_ACCOUNT_ID GO_LIVE_ISO END_DATE
chmod +x "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh"
bash "$ROOT/scripts/dpic/lib/dpi_run_milestone_eod.sh" milestones "$GO_LIVE_ISO" "$END_DATE"

# Assert: at least one posted slice whose end_date is an EMI due that is NOT that installment's own INT due
# (next-due seal ownership) — or month-end seal posted. Soft signal + hard column audit.
read -r next_due_posted <<<"$(
  dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$LOAN_ACCOUNT_ID" <<'SQL'
WITH own_int AS (
  SELECT ldd.loan_installment_details_id AS inst_id, ldd.due_date::date AS due_d
  FROM mfi_accounting.loan_due_details ldd
  WHERE ldd.loan_account_id = :loan_account_id::bigint
    AND ldd.is_deleted = false AND ldd.component_type = 'INT'
),
posted AS (
  SELECT da.installment_id, da.end_date::date AS end_d, da.accrual_posting_date
  FROM mfi_accounting.dpi_accrual_details da
  WHERE da.loan_account_id = :loan_account_id::bigint
    AND da.is_deleted = false AND da.total_accrued_amount > 0
    AND da.accrual_posting_date IS NOT NULL
)
SELECT COUNT(*)::int
FROM posted p
LEFT JOIN own_int oi ON oi.inst_id = p.installment_id
WHERE p.end_d IS DISTINCT FROM oi.due_d
  AND (
    EXTRACT(DAY FROM p.end_d) = EXTRACT(DAY FROM (date_trunc('month', p.end_d) + interval '1 month - 1 day'))
    OR EXISTS (
      SELECT 1 FROM mfi_accounting.loan_due_details d
      WHERE d.loan_account_id = :loan_account_id::bigint AND d.is_deleted = false
        AND d.component_type IN ('INT','PRIN') AND d.due_date::date = p.end_d
    )
  );
SQL
)"
[[ "${next_due_posted:-0}" -gt 0 ]] || fail "no next-due/month-end sealed posted slice (booking anchor miss — 77921d275f class)"

bash "$ROOT/scripts/dpic/lib/run_dpi_column_audit.sh" "$LOAN_ACCOUNT_ID" "$END_DATE" \
  || fail "column audit after booking-anchor EOD"

echo ""
echo "PASS: booking-anchor next-due seal loan=$LOAN_ACCOUNT_ID next_due_or_me_posted=$next_due_posted end=$END_DATE"
