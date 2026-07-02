#!/usr/bin/env bash
# DPIC local preflight — DB product health + service reachability.
# Source from run_setup.sh, run_preflight.sh, or demo scripts.
set -euo pipefail

_DPIC_PF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_DPIC_PF_ROOT="$(cd "$_DPIC_PF_DIR/../../.." && pwd)"

export PGPASSWORD="${PGPASSWORD:-yugabyte}"
DPIC_PG=(psql -h "${YB_HOST:-127.0.0.1}" -p "${YB_PORT:-5433}" -U "${YB_USER:-yugabyte}" -d "${YB_DB:-yugabyte}" -v ON_ERROR_STOP=1)

dpic_http_code() {
  local url="$1" body="${2:-}"
  if [[ -n "$body" ]]; then
    curl -s -m 5 -o /dev/null -w '%{http_code}' -X POST "$url" \
      -H 'Content-Type: application/json' -d "$body" 2>/dev/null || echo 000
  else
    curl -s -m 5 -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo 000
  fi
}

dpic_check_accounting() {
  local base="${ACCOUNTING_BASE_URL:-http://localhost:8002}"
  local body='{"headers":{"tenant_code":"mfi","user_id":"3","stan":"dpic_pf","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"account_number":"6004040825"}}'
  local code
  code="$(dpic_http_code "${base}/accounting/api/v1/getLoanAccountBasicDetails" "$body")"
  if [[ "$code" == "200" ]]; then
    echo "  OK  accounting ${base} (API 200)"
    return 0
  fi
  echo "  FAIL accounting ${base} (HTTP ${code}) — bootRun --args='--spring.profiles.active=mfi'" >&2
  return 1
}

dpic_check_task() {
  local base="${TASK_BASE_URL:-http://localhost:8019}"
  local body='{"headers":{"tenant_code":"mfi","user_id":"53","stan":"dpic_pf","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{}}'
  local code
  code="$(dpic_http_code "${base}/task/api/v1/getTaskList" "$body")"
  if [[ "$code" == "200" ]]; then
    echo "  OK  task ${base} (API 200)"
    return 0
  fi
  echo "  WARN task ${base} (HTTP ${code}) — needed for phase4 reversal; branch mfi_integration_v3.3.1.1" >&2
  return 0
}

dpic_check_actor() {
  local base="${ACTOR_BASE_URL:-http://localhost:8003}"
  local body='{"headers":{"tenant_code":"mfi","user_id":"53","stan":"dpic_pf","client_code":"NOVOPAY","channel_code":"WEB","function_code":"DEFAULT","function_sub_code":"DEFAULT","run_mode":"REAL"},"request":{"user_id":"53"}}'
  local code
  code="$(dpic_http_code "${base}/actor/api/v1/getUserBasicDetails" "$body")"
  if [[ "$code" == "200" ]]; then
    echo "  OK  actor ${base} (API 200)"
    return 0
  fi
  echo "  WARN actor ${base} (HTTP ${code}) — needed for phase4 reversal" >&2
  return 0
}

dpic_check_yugabyte() {
  if "${DPIC_PG[@]}" -c "SELECT 1" >/dev/null 2>&1; then
    echo "  OK  Yugabyte ${YB_HOST:-127.0.0.1}:${YB_PORT:-5433}/${YB_DB:-yugabyte}"
    return 0
  fi
  echo "  FAIL Yugabyte not reachable" >&2
  return 1
}

dpic_check_product_emi() {
  local mult
  mult="$("${DPIC_PG[@]}" -t -A -c \
    "SELECT installment_multiples_of FROM mfi_accounting.loan_product WHERE id=2886" 2>/dev/null || echo MISSING)"
  if [[ "$mult" == "ZERO" || "$mult" == "FIVE" ]]; then
    echo "  OK  loan_product 2886 EMI multiples=$mult"
    return 0
  fi
  if [[ "$mult" == "THOUSAND" ]]; then
    echo "  FAIL loan_product 2886 installment_multiples_of=THOUSAND — causes negative tail PRIN/INT on ₹50k/24mo" >&2
    echo "      Fix: bash scripts/dpic/run_setup.sh" >&2
    return 1
  fi
  echo "  WARN loan_product 2886 EMI multiples=${mult:-?} — expected ZERO for demo payload" >&2
  return 0
}

dpic_check_reversal_schema() {
  local col
  col="$("${DPIC_PG[@]}" -t -A -c \
    "SELECT count(*) FROM information_schema.columns WHERE table_schema='mfi_task' AND table_name='task_activity' AND column_name='activity_initiated_user_role_code'" 2>/dev/null || echo 0)"
  if [[ "$col" == "1" ]]; then
    echo "  OK  task_activity.activity_initiated_user_role_code"
    return 0
  fi
  echo "  WARN task_activity missing activity_initiated_user_role_code — run setup SQL" >&2
  return 0
}

dpic_run_preflight() {
  local fail=0
  echo "=== DPIC preflight ==="
  dpic_check_yugabyte || fail=1
  dpic_check_product_emi || fail=1
  dpic_check_reversal_schema || true
  if [[ "${DPIC_SKIP_SERVICES:-0}" != "1" ]]; then
    dpic_check_accounting || fail=1
    dpic_check_task || true
    dpic_check_actor || true
  fi
  echo ""
  if [[ "$fail" != "0" ]]; then
    echo "Preflight FAILED — fix blockers above before demo." >&2
    return 1
  fi
  echo "Preflight OK."
  return 0
}

dpic_print_next_steps() {
  cat <<'EOF'

Next (live demo — one phase at a time):
  bash scripts/dpic/demo/run_demo.sh status
  bash scripts/dpic/demo/run_demo.sh phase1    # fresh LAN + fast EOD (~25s)
  bash scripts/dpic/demo/run_demo.sh phase2    # APIs (~5s)
  bash scripts/dpic/demo/run_demo.sh phase3    # repayment (~3s)
  bash scripts/dpic/demo/run_demo.sh phase4    # reversal (~5s; needs task :8019)

First-time or after QA dump restore:
  bash scripts/dpic/run_setup.sh

Automation only:
  bash scripts/dpic/demo/run_demo.sh all
EOF
}
