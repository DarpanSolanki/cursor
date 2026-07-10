#!/usr/bin/env bash
# DPI certification — fresh LAN per scenario (no patching one LAN to pass smoke).
#
# Scenarios:
#   pre_emi          — calc before 1st EMI → zero positive accruals
#   single_overdue   — 1 EMI past grace → calc/book/bill + post-EOD verify
#   multi_overdue    — 2 EMIs overdue → multi-installment anchor verify
#
# Usage:
#   bash scripts/dpic/certify_dpi_scenarios.sh           # full certify (3 disburses)
#   bash scripts/dpic/certify_dpi_scenarios.sh --verify-only  # re-run jobs on certified_fixtures.json
#
# Output: scripts/dpic/certified_fixtures.json + registry correlators from primary scenario
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DPIC="$ROOT/dpic"
LIB="$DPIC/lib"
FIXTURES="$DPIC/certified_fixtures.json"
SCRATCH="$ROOT/scratch/dpic_cert"
MODE="${1:-}"
VERIFY_ONLY=0
[[ "$MODE" == "--verify-only" ]] && VERIFY_ONLY=1

export PGPASSWORD="${PGPASSWORD:-yugabyte}"
PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}")
NTEST="$ROOT/bin/ntest.sh"
WAIT_BATCH="$DPIC/lib/wait_batch_job.sh"
ANCHOR_DATE="${ANCHOR_DATE:-$(date +%Y-%m-%d)}"
GRACE_DAYS="${GRACE_DAYS:-3}"
export DEMO_QUIET=1

fail() { echo "FAIL: $*" >&2; exit 1; }

accrued_positive() {
  local lid="$1"
  "${PG[@]}" -t -A -c \
    "SELECT COUNT(*) FROM mfi_accounting.dpi_accrual_details
     WHERE loan_account_id=$lid AND is_deleted=false AND total_accrued_amount>0;"
}

run_calc_only() {
  local lid="$1" jt="$2"
  # shellcheck disable=SC1091
  source "$LIB/dpi_demo_fixture.sh"
  local product_code
  read -r product_code <<<"$(
    dpi_pg -t -A -v ON_ERROR_STOP=1 -v loan_account_id="$lid" <<'SQL'
SELECT COALESCE(p.code, '7676')
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
LEFT JOIN mfi_accounting.product p ON p.id = lp.product_id AND p.is_deleted = false
WHERE la.account_id = :loan_account_id::bigint;
SQL
  )"
  dpi_set_go_live_and_refresh "15-04-2025" "${product_code:-7676}"
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$lid" \
    -f "$DPIC/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
  dpi_pg -v ON_ERROR_STOP=1 -v loan_account_id="$lid" -v business_date_ms="$jt" \
    -f "$DPIC/sql/helpers/sync_demo_past_due.sql" >/dev/null
  dpi_call_batch dpiAccrualCalculation "$jt"
}

run_full_eod() {
  local lid="$1" jt="$2"
  LOAN_ACCOUNT_ID="$lid" JOB_TIME="$jt" SEED_CALC_WINDOW=0 SYNC_PAST_DUE=1 QUARANTINE_PORTFOLIO=1 RESET_DPI_BOOKING=1 \
    bash "$DPIC/run_eod_dpi_only.sh"
}

setup_grace() {
  local lid="$1"
  "${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$lid" -v grace_days="$GRACE_DAYS" \
    -f "$DPIC/sql/helpers/setup_grace_dpi_e2e.sql" >/dev/null
  "${PG[@]}" -v ON_ERROR_STOP=1 -v loan_account_id="$lid" \
    -f "$DPIC/sql/helpers/quarantine_dpd_portfolio.sql" >/dev/null
}

write_scenario() {
  local id="$1" status="$2"
  shift 2
  mkdir -p "$SCRATCH"
  local tmp="$SCRATCH/${id}.json"
  python3 - "$tmp" "$id" "$status" "$@" <<'PY'
import json, os, sys
path, sid, status = sys.argv[1], sys.argv[2], sys.argv[3]
kv = {}
for arg in sys.argv[4:]:
    k, _, v = arg.partition("=")
    kv[k] = v
doc = {"id": sid, "status": status, **kv}
json.dump(doc, open(path, "w"), indent=2)
print(path)
PY
  python3 "$LIB/write_certified_fixtures.py" "$FIXTURES" "$tmp" "${PRIMARY_SCENARIO:-}"
}

sync_registry() {
  [[ -f "$FIXTURES" ]] || return 0
  python3 - "$FIXTURES" "$ROOT/testing/registry.json" <<'PY'
import json, sys
from pathlib import Path
fx = json.loads(Path(sys.argv[1]).read_text())
reg = json.loads(Path(sys.argv[2]).read_text())
p = fx.get("primary") or {}
c = reg.setdefault("_correlators", {})
for k, fk in [("ACCOUNT_NUMBER", "lan"), ("LOAN_ACCOUNT_ID", "loan_account_id"),
              ("FORECLOSURE_DATE", "foreclosure_date"), ("JOB_TIME", "job_time")]:
    if p.get(fk):
        c[k] = str(p[fk])
Path(sys.argv[2]).write_text(json.dumps(reg, indent=2) + "\n", encoding="utf-8")
print("registry correlators ← primary certified LAN", p.get("lan", "?"))
PY
}

certify_pre_emi() {
  echo ""
  echo "=== CERTIFY: pre_emi (fresh LAN) ==="
  if [[ "$VERIFY_ONLY" == "1" ]]; then
    local lid lan jt
    lid="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['loan_account_id'] for s in d['scenarios'] if s['id']=='pre_emi'))")"
    lan="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['lan'] for s in d['scenarios'] if s['id']=='pre_emi'))")"
    jt="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['pre_emi_job_ms'] for s in d['scenarios'] if s['id']=='pre_emi'))")"
  else
    # shellcheck disable=SC1091
    source "$LIB/disburse_fresh_dpi_loan.sh" pre_emi
    eval "$(LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" python3 "$LIB/job_times_from_loan.py")"
    jt="$PRE_EMI_JOB_MS"
    lid="$LOAN_ACCOUNT_ID"
    lan="$LAN"
  fi
  run_calc_only "$lid" "$jt"
  local n
  n="$(accrued_positive "$lid")"
  [[ "${n:-0}" == "0" ]] || fail "pre_emi: expected 0 positive accruals, got $n on $lan"
  write_scenario pre_emi PASS \
    lan="$lan" loan_account_id="$lid" ext_ref="${EXT_REF:-}" customer_id="${CUSTOMER_ID:-}" \
    pre_emi_job_ms="$jt" anchor_date="$ANCHOR_DATE" assertion="zero_accrual_before_first_emi"
  echo "PASS pre_emi lan=$lan"
}

certify_single_overdue() {
  echo ""
  echo "=== CERTIFY: single_overdue (fresh LAN) ==="
  if [[ "$VERIFY_ONLY" == "1" ]]; then
    local lid lan jt
    lid="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['loan_account_id'] for s in d['scenarios'] if s['id']=='single_overdue'))")"
    lan="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['lan'] for s in d['scenarios'] if s['id']=='single_overdue'))")"
    jt="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['single_overdue_job_ms'] for s in d['scenarios'] if s['id']=='single_overdue'))")"
  else
    source "$LIB/disburse_fresh_dpi_loan.sh" single_overdue
    setup_grace "$LOAN_ACCOUNT_ID"
    eval "$(LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" python3 "$LIB/job_times_from_loan.py")"
    jt="$SINGLE_OVERDUE_JOB_MS"
    lid="$LOAN_ACCOUNT_ID"
    lan="$LAN"
  fi
  setup_grace "$lid"
  run_full_eod "$lid" "$jt"
  local n
  n="$(accrued_positive "$lid")"
  [[ "${n:-0}" -gt 0 ]] || fail "single_overdue: expected positive accruals on $lan"
  export LOAN_ACCOUNT_ID="$lid"
  _out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' -v loan_account_id="$lid" \
    -f "$DPIC/sql/helpers/verify_dpi_post_eod.sql" | tail -1)"
  _accrual="${_out%%|*}"
  [[ "${_accrual:-0}" -gt 0 ]] || fail "single_overdue: post-EOD verify accrual_rows=0 on $lan"
  write_scenario single_overdue PASS \
    lan="$lan" loan_account_id="$lid" ext_ref="${EXT_REF:-}" customer_id="${CUSTOMER_ID:-}" \
    single_overdue_job_ms="$jt" foreclosure_job_ms="${FORECLOSURE_JOB_MS:-$jt}" \
    anchor_date="$ANCHOR_DATE" assertion="full_eod_positive_accrual"
  echo "PASS single_overdue lan=$lan accrual_rows=$_accrual"
  export PRIMARY_SCENARIO=single_overdue
}

certify_multi_overdue() {
  echo ""
  echo "=== CERTIFY: multi_overdue (fresh LAN) ==="
  if [[ "$VERIFY_ONLY" == "1" ]]; then
    local lid lan jt
    lid="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['loan_account_id'] for s in d['scenarios'] if s['id']=='multi_overdue'))")"
    lan="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['lan'] for s in d['scenarios'] if s['id']=='multi_overdue'))")"
    jt="$(python3 -c "import json; d=json.load(open('$FIXTURES')); print(next(s['multi_overdue_job_ms'] for s in d['scenarios'] if s['id']=='multi_overdue'))")"
  else
    source "$LIB/disburse_fresh_dpi_loan.sh" multi_overdue
    setup_grace "$LOAN_ACCOUNT_ID"
    eval "$(LOAN_ACCOUNT_ID="$LOAN_ACCOUNT_ID" python3 "$LIB/job_times_from_loan.py")"
    jt="$MULTI_OVERDUE_JOB_MS"
    lid="$LOAN_ACCOUNT_ID"
    lan="$LAN"
  fi
  setup_grace "$lid"
  "${PG[@]}" -v ON_ERROR_STOP=1 -t -A -v loan_account_id="$lid" \
    -f "$DPIC/sql/helpers/purge_dpi_accruals_for_loan.sql" >/dev/null || true
  run_calc_only "$lid" "$jt"
  local verify_out emi1 emi2 r1 r2 latest
  for _ in $(seq 1 25); do
    verify_out="$("${PG[@]}" -v ON_ERROR_STOP=1 -t -A -F'|' -v loan_account_id="$lid" \
      -f "$DPIC/sql/helpers/verify_multi_emi_installment_dpi_e2e.sql" | tail -1)"
    IFS='|' read -r emi1 emi2 r1 r2 latest <<<"$verify_out"
    [[ "${r1:-0}" -gt 0 && "${r2:-0}" -gt 0 && "$latest" == "$emi2" ]] && break
    sleep 1
  done
  [[ "${r1:-0}" -gt 0 && "${r2:-0}" -gt 0 ]] || fail "multi_overdue: need accruals on EMI1 and EMI2 (lan=$lan)"
  [[ "$latest" == "$emi2" ]] || fail "multi_overdue: latest installment should be EMI2 ($emi2) got $latest"
  write_scenario multi_overdue PASS \
    lan="$lan" loan_account_id="$lid" ext_ref="${EXT_REF:-}" customer_id="${CUSTOMER_ID:-}" \
    multi_overdue_job_ms="$jt" anchor_date="$ANCHOR_DATE" \
    assertion="multi_emi_anchor_on_latest_overdue" emi1_rows="$r1" emi2_rows="$r2"
  echo "PASS multi_overdue lan=$lan emi1=$r1 emi2=$r2 latest=$latest"
}

echo "=== DPI scenario certification (anchor=$ANCHOR_DATE) ==="
bash "$ROOT/bin/novopay-service.sh" ensure accounting ${COMPILE:+--compile}

if [[ "$VERIFY_ONLY" != "1" && "${SKIP_SETUP:-0}" != "1" ]]; then
  echo ">>> One-time product/rules setup (SKIP_SETUP=1 to skip)"
  bash "$DPIC/run_setup.sh" 2>&1 | tail -4
fi

chmod +x "$LIB/disburse_fresh_dpi_loan.sh" "$LIB/job_times_from_loan.py" "$LIB/write_certified_fixtures.py"

certify_pre_emi
certify_single_overdue
certify_multi_overdue

sync_registry

echo ""
echo "=== DPI certification PASS ==="
echo "  fixtures: $FIXTURES"
python3 -c "import json; d=json.load(open('$FIXTURES')); print('  scenarios:', ', '.join(f\"{s['id']}:{s['lan']}\" for s in d['scenarios']))"
echo ""
echo "Re-verify without new disburses: bash scripts/dpic/certify_dpi_scenarios.sh --verify-only"
