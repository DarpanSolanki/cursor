#!/usr/bin/env bash
# Fixture for restructuring.loan_account_restructuring_tenure.
#
# Proposal path when merged: scripts/testing/flowtest/run_restructuring_tenure_fixture.sh
#
# Brings ${LAN} to the state the APPROVE leg requires, then fires the DEFAULT/REAL
# create leg. It seeds PRECONDITIONS only. Every row the assert reads
# (loan_account_restructuring_details, loan_account_reschedule_details,
# loan_installment_details) is written by the real orchestration, never by this script.
#
# Env: LAN (required), USER_ID (default 103), EFFECTIVE_DATE (default today, ISO),
#      NEW_TENURE (default 24)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

LAN="${LAN:?LAN required}"
USER_ID="${USER_ID:-103}"
EFFECTIVE_DATE="${EFFECTIVE_DATE:-$(date +%F)}"
NEW_TENURE="${NEW_TENURE:-24}"
SCRATCH="$ROOT/scripts/scratch/restructuring"
mkdir -p "$SCRATCH"

acct_id="$(bash scripts/db-local.sh --sql \
  "SELECT la.account_id FROM mfi_accounting.loan_account la
   JOIN mfi_accounting.account a ON a.id = la.account_id
   WHERE a.account_number = '${LAN}'" | sed -n '3p' | tr -d ' ')"
[[ -n "$acct_id" ]] || { echo "FAIL: no loan_account for LAN=${LAN}"; exit 1; }

# 1. product capability: 134371 is thrown when loan_restructuring_allowed = false.
#    The row is cached in Redis db 5 + Spring accountingCacheManager, so evict after
#    the UPDATE or the API keeps serving the pre-change flag (GAP-058 class).
cat > "$SCRATCH/_fixture_product.sql" <<SQL
UPDATE mfi_accounting.loan_product lp
SET loan_restructuring_allowed = true, updated_by = 'RSTR_FIXTURE', updated_on = NOW()
FROM mfi_accounting.loan_account la
WHERE la.account_id = ${acct_id} AND lp.id = la.loan_product_id
  AND lp.loan_restructuring_allowed = false;
SQL
bash scripts/bin/db-local-write.sh --file "$SCRATCH/_fixture_product.sql" >/dev/null
redis-cli -n 5 --scan --pattern 'loan_product::*' | xargs -r redis-cli -n 5 del >/dev/null
redis-cli -n 5 --scan --pattern '*product_id_*' | xargs -r redis-cli -n 5 del >/dev/null

# 2. accrual must be up to date to the effective date, or
#    ValidateLoanRestructuringBusinessCaseProcessor:190 throws 134205. One fire of the
#    real job accrues disbursement-date -> job-date in a single pass.
JOB_MS="$(python3 -c "
from datetime import datetime,timezone,timedelta
d=datetime.fromisoformat('${EFFECTIVE_DATE}')
print(int(d.replace(hour=18,tzinfo=timezone(timedelta(hours=5,minutes=30))).timestamp()*1000))")"
PYTHONPATH="$ROOT/scripts/testing:$ROOT/scripts/dcf_sanity" python3 -c "
from flowtest.dateroll import fire_and_wait
fire_and_wait('interestAccrualCalculation','${JOB_MS}',timeout_s=400,soft_fail=False)"

accr="$(bash scripts/db-local.sh --sql \
  "SELECT max(end_date)::date FROM mfi_accounting.interest_accrual_details
   WHERE account_id = ${acct_id}" | sed -n '3p' | tr -d ' ')"
[[ "$accr" == "$EFFECTIVE_DATE" ]] || {
  echo "FAIL: accrual tip ${accr:-none} != effective date ${EFFECTIVE_DATE} (134205 would fire)"; exit 1; }

EFF_MS="$(python3 -c "
from datetime import datetime,timezone,timedelta
d=datetime.fromisoformat('${EFFECTIVE_DATE}')
print(int(d.replace(tzinfo=timezone(timedelta(hours=5,minutes=30))).timestamp()*1000))")"

# 3. bpi_amount is validated fail-closed against the system value (134364). Read it
#    from the flow itself rather than hardcoding an environment-dependent number.
OLD_TENURE="$(bash scripts/db-local.sh --sql \
  "SELECT number_of_installments FROM mfi_accounting.loan_account
   WHERE account_id = ${acct_id}" | sed -n '3p' | tr -d ' ')"

write_payload() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys
out, fn_code, bpi = sys.argv[1], sys.argv[2], sys.argv[3]
import os
json.dump({
  "headers": {
    "actor_type": "CUSTOMER", "operation_mode": "SELF", "channel_code": "WEB",
    "function_code": fn_code, "function_sub_code": "DEFAULT", "run_mode": "REAL",
    "user_id": os.environ["USER_ID"], "stan": "{{$timestamp}}",
    "tenant_code": "mfi", "client_code": "NOVOPAY",
    "transmission_datetime": os.environ["EFF_MS"],
  },
  "request": {"loan_account_restructuring": {
    "loan_account_number": os.environ["LAN"],
    "rescheduling_effective_date": os.environ["EFF_MS"],
    "restructuring_impact": "UPDATE_TENURE",
    "excess_amount": "0", "bpi_amount": bpi, "overdue_amount": "0",
    "due_amount": "0", "penal_amount": "0", "fee_amount": "0",
    "old_tenure": os.environ["OLD_TENURE"], "new_tenure": os.environ["NEW_TENURE"],
    "is_roi_changed": "false", "reason": "BORROWER_STRUGGLES_TO_PAY",
    "notes": "Restructuring tenure coverage",
  }},
}, open(out, "w"), indent=1)
PY
}
export USER_ID EFF_MS LAN OLD_TENURE NEW_TENURE

write_payload "$SCRATCH/_probe.json" DEFAULT 0
probe="$(TRIAL=1 python3 - <<'PY'
import json, subprocess, re
p = "scripts/scratch/restructuring/_probe.json"
d = json.load(open(p)); d["headers"]["run_mode"] = "TRIAL"; json.dump(d, open(p, "w"))
o = subprocess.run(["python3", "scripts/testing/api-fire.py",
                    "loanAccountRestructuring", "-f", p],
                   capture_output=True, text=True).stdout
m = re.search(r"calculated value : ([0-9.]+)", o)
print(m.group(1) if m else "0")
PY
)"
echo "  bpi_amount resolved from flow = ${probe}"

write_payload "$SCRATCH/restructuring_tenure_create.json" DEFAULT "$probe"
write_payload "$SCRATCH/restructuring_tenure_approve.json" APPROVE "$probe"

python3 scripts/testing/api-fire.py loanAccountRestructuring \
  -f "$SCRATCH/restructuring_tenure_create.json" | tail -2

pending="$(bash scripts/db-local.sh --sql \
  "SELECT count(*) FROM mfi_accounting.loan_account_restructuring_details
   WHERE loan_account_id = ${acct_id} AND restructuring_status = 'PENDING'
     AND is_deleted = false" | sed -n '3p' | tr -d ' ')"
[[ "$pending" == "1" ]] || { echo "FAIL: expected 1 PENDING restructuring row, got ${pending}"; exit 1; }
echo "=== PASS: fixture ready — APPROVE payload at ${SCRATCH}/restructuring_tenure_approve.json"
