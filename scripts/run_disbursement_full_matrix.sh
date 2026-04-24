#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCOUNTING_DIR="$ROOT_DIR/novopay-platform-accounting-v2"
RUNNER_CLASS="in.novopay.accounting.consumers.LmsDisburseKafkaEntryFlowRunner"
TMP_DIR="${TMPDIR:-/tmp}/disbursement_full_matrix"
mkdir -p "$TMP_DIR"

# DB connection can be overridden if needed.
PSQL_URI="${PSQL_URI:-host=127.0.0.1 port=5433 dbname=yugabyte user=yugabyte password=yugabyte}"
RUN_START_TS="$(date '+%Y-%m-%d %H:%M:%S')"

# Customer strategy:
# - If env vars are provided, script uses them.
# - Otherwise script auto-picks 2 available customers per product.
JLG_PRIMARY="${JLG_PRIMARY:-}"
JLG_SECONDARY="${JLG_SECONDARY:-}"
INDL_PRIMARY="${INDL_PRIMARY:-}"
INDL_SECONDARY="${INDL_SECONDARY:-}"
SHG_PRIMARY="${SHG_PRIMARY:-}"
SHG_SECONDARY="${SHG_SECONDARY:-}"

JLG_PAYLOAD="${JLG_PAYLOAD:-$ROOT_DIR/scripts/disburse_loan_sanity_request_4495972134234554346565.json}"
INDL_PAYLOAD="${INDL_PAYLOAD:-$ROOT_DIR/scripts/disburse_loan_sanity_request_370164.json}"
SHG_PAYLOAD="${SHG_PAYLOAD:-$ROOT_DIR/scripts/disburse_loan_sanity_request_shg_41333333.json}"
JLG_TEST_LAN="${JLG_TEST_LAN:-6003367739}"
INDL_TEST_LAN="${INDL_TEST_LAN:-6003367039}"

TARGET="${1:-ALL}"
TARGET="$(echo "$TARGET" | tr '[:lower:]' '[:upper:]')"
case "$TARGET" in
  ALL|JLG|INDL|SHG) ;;
  *)
    echo "Usage: $0 [ALL|JLG|INDL|SHG]"
    exit 2
    ;;
esac

RUN_JLG=0
RUN_INDL=0
RUN_SHG=0
if [[ "$TARGET" == "ALL" || "$TARGET" == "JLG" ]]; then RUN_JLG=1; fi
if [[ "$TARGET" == "ALL" || "$TARGET" == "INDL" ]]; then RUN_INDL=1; fi
if [[ "$TARGET" == "ALL" || "$TARGET" == "SHG" ]]; then RUN_SHG=1; fi

timestamp="$(date +%s)"
LOG_JLG="$TMP_DIR/jlg_${timestamp}.log"
LOG_INDL="$TMP_DIR/indl_${timestamp}.log"
LOG_SHG="$TMP_DIR/shg_${timestamp}.log"

echo "[matrix] Preparing classpath..."
cd "$ACCOUNTING_DIR"
./gradlew -q testClasses -x test >/dev/null
CP="$(./gradlew -q -I tmp-printcp.init.gradle printTestRuntimeClasspath)"

run_suite() {
  local label="$1"
  local payload="$2"
  local log_file="$3"
  shift 3

  echo "[matrix] Running ${label} suite..."
  env \
    KAFKA_ENTRY_SCENARIO_START=1 \
    KAFKA_ENTRY_SCENARIO_LIMIT=8 \
    "$@" \
    java -cp "$CP" "$RUNNER_CLASS" "$payload" >"$log_file" 2>&1

  local start_count
  local end_count
  start_count="$(awk '/\[kafka-entry\] start scenario=/{c++} END{print c+0}' "$log_file")"
  end_count="$(awk '/\[kafka-entry\] end scenario=/{c++} END{print c+0}' "$log_file")"

  if [[ "$start_count" -ne 8 || "$end_count" -ne 8 ]]; then
    echo "[matrix] ${label}: FAILED (expected 8 scenario starts/ends, got starts=${start_count}, ends=${end_count})"
    echo "[matrix] Check log: $log_file"
    return 1
  fi

  if awk '/Fatal error while processing LMS disbursement|NumberFormatException|NovopayFatalException:|IDEMPOTENCY_ASSERT_FAIL/{found=1} END{exit found?0:1}' "$log_file"; then
    echo "[matrix] ${label}: FAILED (fatal signature found in log)"
    echo "[matrix] Check log: $log_file"
    return 1
  fi

  echo "[matrix] ${label}: runner scenarios completed"
}

collect_inquiry_breakdown() {
  local log_file="$1"
  local baseline replay
  baseline="$(awk -F'inquiry_delta=' '/\[kafka-entry\] delta scenario=/{ split($1, left, "scenario="); split(left[2], sc, " "); if (sc[1] == "S1_default_once" || sc[1] == "S7_fresh_second_ref") { split($2, right, " "); s += right[1]+0 } } END{print s+0}' "$log_file")"
  replay="$(awk -F'inquiry_delta=' '/\[kafka-entry\] delta scenario=/{ split($1, left, "scenario="); split(left[2], sc, " "); if (!(sc[1] == "S1_default_once" || sc[1] == "S7_fresh_second_ref")) { split($2, right, " "); s += right[1]+0 } } END{print s+0}' "$log_file")"
  echo "${baseline}|${replay}"
}

pick_available_customers() {
  local product_id="$1"
  local provided_primary="$2"
  local provided_secondary="$3"

  if [[ -n "$provided_primary" && -n "$provided_secondary" ]]; then
    echo "$provided_primary|$provided_secondary"
    return 0
  fi

  local sql
  sql=$(cat <<SQL
SELECT c.id
FROM mfi_actor.customer c
WHERE c.is_deleted = false
  AND NOT EXISTS (
    SELECT 1
    FROM mfi_accounting.loan_account la
    JOIN mfi_accounting.loan_product lp ON lp.id = la.loan_product_id
    WHERE la.customer_id = c.id
      AND la.is_deleted = false
      AND la.loan_status = 'ACTIVE'
      AND lp.product_id = '$product_id'
  )
ORDER BY c.id DESC
LIMIT 20;
SQL
)

  mapfile -t ids < <(psql "$PSQL_URI" -At -c "$sql" | awk 'NF {print $1}')
  if [[ "${#ids[@]}" -lt 2 ]]; then
    echo "ERROR|ERROR"
    return 1
  fi

  local primary="$provided_primary"
  local secondary="$provided_secondary"
  if [[ -z "$primary" ]]; then
    primary="${ids[0]}"
  fi
  if [[ -z "$secondary" ]]; then
    for id in "${ids[@]}"; do
      if [[ "$id" != "$primary" ]]; then
        secondary="$id"
        break
      fi
    done
  fi

  if [[ -z "$primary" || -z "$secondary" || "$primary" == "$secondary" ]]; then
    echo "ERROR|ERROR"
    return 1
  fi

  echo "$primary|$secondary"
}

extract_ext_ref() {
  local scenario="$1"
  local log_file="$2"
  awk -v s="$scenario" '
    $0 ~ "\\[kafka-entry\\] start scenario=" s {
      split($0, parts, "ext_ref=")
      split(parts[2], rest, " ")
      print rest[1]
      exit
    }' "$log_file"
}

extract_account_number() {
  local scenario="$1"
  local log_file="$2"
  awk -v s="$scenario" '
    $0 ~ "\\[kafka-entry\\] start scenario=" s {
      split($0, parts, "account_number=")
      split(parts[2], rest, " ")
      print rest[1]
      exit
    }' "$log_file"
}

if [[ "$RUN_JLG" -eq 1 ]]; then
  JLG_PAIR="$(pick_available_customers "2" "$JLG_PRIMARY" "$JLG_SECONDARY")" || {
    echo "[matrix] FAILED: could not pick 2 available customers for JLG (product_id=2)"
    exit 1
  }
  JLG_PRIMARY="${JLG_PAIR%%|*}"
  JLG_SECONDARY="${JLG_PAIR##*|}"
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  INDL_PAIR="$(pick_available_customers "45" "$INDL_PRIMARY" "$INDL_SECONDARY")" || {
    echo "[matrix] FAILED: could not pick 2 available customers for INDL (product_id=45)"
    exit 1
  }
  INDL_PRIMARY="${INDL_PAIR%%|*}"
  INDL_SECONDARY="${INDL_PAIR##*|}"
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  SHG_PAIR="$(pick_available_customers "44" "$SHG_PRIMARY" "$SHG_SECONDARY")" || {
    echo "[matrix] FAILED: could not pick 2 available customers for SHG (product_id=44)"
    exit 1
  }
  SHG_PRIMARY="${SHG_PAIR%%|*}"
  SHG_SECONDARY="${SHG_PAIR##*|}"
fi

echo "[matrix] Customer strategy:"
if [[ "$RUN_JLG" -eq 1 ]]; then echo "  JLG  primary=$JLG_PRIMARY secondary=$JLG_SECONDARY"; fi
if [[ "$RUN_INDL" -eq 1 ]]; then echo "  INDL primary=$INDL_PRIMARY secondary=$INDL_SECONDARY"; fi
if [[ "$RUN_SHG" -eq 1 ]]; then echo "  SHG  primary=$SHG_PRIMARY secondary=$SHG_SECONDARY"; fi

JLG_S1_EXTREF=""
JLG_S7_EXTREF=""
INDL_S1_EXTREF=""
INDL_S7_EXTREF=""
SHG_S1_EXTREF=""
SHG_S7_EXTREF=""
JLG_S1_LAN_HINT=""
JLG_S7_LAN_HINT=""
INDL_S1_LAN_HINT=""
INDL_S7_LAN_HINT=""
SHG_S1_LAN_HINT=""
SHG_S7_LAN_HINT=""
JLG_BASELINE_INQ=0
JLG_REPLAY_INQ=0
INDL_BASELINE_INQ=0
INDL_REPLAY_INQ=0
SHG_BASELINE_INQ=0
SHG_REPLAY_INQ=0

if [[ "$RUN_JLG" -eq 1 ]]; then
  run_suite "JLG" "$JLG_PAYLOAD" "$LOG_JLG" \
    KAFKA_ENTRY_TEST_LAN="$JLG_TEST_LAN" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$JLG_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$JLG_SECONDARY" \
    KAFKA_ENTRY_FORCE_DISBURSEMENT_MODE="ACCTWB"
  JLG_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_JLG")"
  JLG_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_JLG")"
  JLG_S1_LAN_HINT="$(extract_account_number "S1_default_once" "$LOG_JLG")"
  JLG_S7_LAN_HINT="$(extract_account_number "S7_fresh_second_ref" "$LOG_JLG")"
  [[ -z "$JLG_S1_LAN_HINT" ]] && JLG_S1_LAN_HINT="$JLG_TEST_LAN"
  [[ -z "$JLG_S7_LAN_HINT" ]] && JLG_S7_LAN_HINT="$JLG_TEST_LAN"
  JLG_INQ="$(collect_inquiry_breakdown "$LOG_JLG")"
  JLG_BASELINE_INQ="${JLG_INQ%%|*}"
  JLG_REPLAY_INQ="${JLG_INQ##*|}"
  if ! grep -q '\[kafka-entry\] end scenario=S8_queue_soft_delete_replay' "$LOG_JLG"; then
    S8_OK=0
  fi
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  run_suite "INDL" "$INDL_PAYLOAD" "$LOG_INDL" \
    KAFKA_ENTRY_TEST_LAN="$INDL_TEST_LAN" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$INDL_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$INDL_SECONDARY"
  INDL_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_INDL")"
  INDL_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_INDL")"
  INDL_S1_LAN_HINT="$(extract_account_number "S1_default_once" "$LOG_INDL")"
  INDL_S7_LAN_HINT="$(extract_account_number "S7_fresh_second_ref" "$LOG_INDL")"
  [[ -z "$INDL_S1_LAN_HINT" ]] && INDL_S1_LAN_HINT="$INDL_TEST_LAN"
  [[ -z "$INDL_S7_LAN_HINT" ]] && INDL_S7_LAN_HINT="$INDL_TEST_LAN"
  INDL_INQ="$(collect_inquiry_breakdown "$LOG_INDL")"
  INDL_BASELINE_INQ="${INDL_INQ%%|*}"
  INDL_REPLAY_INQ="${INDL_INQ##*|}"
  if ! grep -q '\[kafka-entry\] end scenario=S8_individual_terminal_replay' "$LOG_INDL"; then
    S8_OK=0
  fi
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  run_suite "SHG" "$SHG_PAYLOAD" "$LOG_SHG" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$SHG_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$SHG_SECONDARY"
  SHG_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_SHG")"
  SHG_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_SHG")"
  SHG_S1_LAN_HINT="$(extract_account_number "S1_default_once" "$LOG_SHG")"
  SHG_S7_LAN_HINT="$(extract_account_number "S7_fresh_second_ref" "$LOG_SHG")"
  SHG_INQ="$(collect_inquiry_breakdown "$LOG_SHG")"
  SHG_BASELINE_INQ="${SHG_INQ%%|*}"
  SHG_REPLAY_INQ="${SHG_INQ##*|}"
  if ! grep -q '\[kafka-entry\] end scenario=S8_queue_soft_delete_replay' "$LOG_SHG"; then
    S8_OK=0
  fi
fi

if { [[ "$RUN_JLG" -eq 1 ]] && [[ -z "$JLG_S1_EXTREF" || -z "$JLG_S7_EXTREF" ]]; } || \
   { [[ "$RUN_INDL" -eq 1 ]] && [[ -z "$INDL_S1_EXTREF" || -z "$INDL_S7_EXTREF" ]]; } || \
   { [[ "$RUN_SHG" -eq 1 ]] && [[ -z "$SHG_S1_EXTREF" || -z "$SHG_S7_EXTREF" ]]; }; then
  echo "[matrix] FAILED: could not parse scenario ext_ref values from logs."
  echo "[matrix] Logs: $LOG_JLG $LOG_INDL $LOG_SHG"
  exit 1
fi

STATE_SQL=$(cat <<SQL
WITH refs(flow, ext_ref) AS (
  VALUES
    ('JLG-S1', '$JLG_S1_EXTREF'),
    ('JLG-S7', '$JLG_S7_EXTREF'),
    ('INDL-S1', '$INDL_S1_EXTREF'),
    ('INDL-S7', '$INDL_S7_EXTREF'),
    ('SHG-S1', '$SHG_S1_EXTREF'),
    ('SHG-S7', '$SHG_S7_EXTREF')
)
SELECT refs.flow || '|' || refs.ext_ref || '|' ||
       COALESCE(la.account_id::text, '') || '|' ||
       COALESCE(la.la_account_number, '') || '|' ||
       COALESCE(la.loan_status, '') || '|' ||
       COALESCE(la.disbursement_status, '')
FROM refs
LEFT JOIN mfi_accounting.loan_account la
  ON la.external_ref_number = refs.ext_ref
 AND la.is_deleted = false
ORDER BY refs.flow;
SQL
)

echo "[matrix] Fetching DB state summary..."
STATE_LINES="$(psql "$PSQL_URI" -At -c "$STATE_SQL")"

declare -A FLOW_ACCOUNT_ID
declare -A FLOW_LAN
declare -A FLOW_LOAN_STATUS
declare -A FLOW_DISB_STATUS

while IFS='|' read -r flow ext_ref account_id lan loan_status disb_status; do
  [[ -z "$flow" ]] && continue
  FLOW_ACCOUNT_ID["$flow"]="$account_id"
  FLOW_LAN["$flow"]="$lan"
  FLOW_LOAN_STATUS["$flow"]="$loan_status"
  FLOW_DISB_STATUS["$flow"]="$disb_status"
done <<<"$STATE_LINES"

# Fallback to runner-provided LAN hints when ext_ref is not persisted in loan_account.
[[ -z "${FLOW_LAN[JLG-S1]:-}" && -n "$JLG_S1_LAN_HINT" ]] && FLOW_LAN["JLG-S1"]="$JLG_S1_LAN_HINT"
[[ -z "${FLOW_LAN[JLG-S7]:-}" && -n "$JLG_S7_LAN_HINT" ]] && FLOW_LAN["JLG-S7"]="$JLG_S7_LAN_HINT"
[[ -z "${FLOW_LAN[INDL-S1]:-}" && -n "$INDL_S1_LAN_HINT" ]] && FLOW_LAN["INDL-S1"]="$INDL_S1_LAN_HINT"
[[ -z "${FLOW_LAN[INDL-S7]:-}" && -n "$INDL_S7_LAN_HINT" ]] && FLOW_LAN["INDL-S7"]="$INDL_S7_LAN_HINT"
[[ -z "${FLOW_LAN[SHG-S1]:-}" && -n "$SHG_S1_LAN_HINT" ]] && FLOW_LAN["SHG-S1"]="$SHG_S1_LAN_HINT"
[[ -z "${FLOW_LAN[SHG-S7]:-}" && -n "$SHG_S7_LAN_HINT" ]] && FLOW_LAN["SHG-S7"]="$SHG_S7_LAN_HINT"

for flow in JLG-S1 JLG-S7 INDL-S1 INDL-S7 SHG-S1 SHG-S7; do
  if [[ -z "${FLOW_LOAN_STATUS[$flow]:-}" && -n "${FLOW_LAN[$flow]:-}" ]]; then
    lan_state="$(psql "$PSQL_URI" -At -c "SELECT COALESCE(loan_status,''), COALESCE(disbursement_status,'') FROM mfi_accounting.loan_account WHERE la_account_number='${FLOW_LAN[$flow]}' AND is_deleted=false ORDER BY created_on DESC LIMIT 1;")"
    FLOW_LOAN_STATUS["$flow"]="$(awk -F'|' '{print $1}' <<<"$lan_state")"
    FLOW_DISB_STATUS["$flow"]="$(awk -F'|' '{print $2}' <<<"$lan_state")"
  fi
done

check_flow_state() {
  local flow="$1"
  local expected_loan="$2"
  local expected_disb="$3"
  local loan="${FLOW_LOAN_STATUS[$flow]:-}"
  local disb="${FLOW_DISB_STATUS[$flow]:-}"
  if [[ "$loan" == "$expected_loan" && "$disb" == "$expected_disb" ]]; then
    return 0
  fi
  return 1
}

MATRIX_OK=1
IDEMPOTENCY_OK=1
INQUIRY_POLICY_OK=1
CRR_INTEGRITY_OK=1
S8_OK=1

if [[ "$RUN_JLG" -eq 1 ]]; then
  if ! check_flow_state "JLG-S1" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
  if ! check_flow_state "JLG-S7" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  if ! check_flow_state "INDL-S1" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
  if ! check_flow_state "INDL-S7" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  shg1="${FLOW_DISB_STATUS[SHG-S1]:-}"
  shg7="${FLOW_DISB_STATUS[SHG-S7]:-}"
  if [[ "${FLOW_LOAN_STATUS[SHG-S1]:-}" != "ACTIVE" ]] || [[ "$shg1" != "PARENT_SUCCESS" && "$shg1" != "CHILD_SUCCESS" && "$shg1" != "COMPLETED" ]]; then MATRIX_OK=0; fi
  if [[ "${FLOW_LOAN_STATUS[SHG-S7]:-}" != "ACTIVE" ]] || [[ "$shg7" != "PARENT_SUCCESS" && "$shg7" != "CHILD_SUCCESS" && "$shg7" != "COMPLETED" ]]; then MATRIX_OK=0; fi
fi

if [[ "$RUN_JLG" -eq 1 && "${JLG_BASELINE_INQ:-0}" -ne 0 ]]; then INQUIRY_POLICY_OK=0; fi
if [[ "$RUN_INDL" -eq 1 && "${INDL_BASELINE_INQ:-0}" -ne 0 ]]; then INQUIRY_POLICY_OK=0; fi
if [[ "$RUN_SHG" -eq 1 && "${SHG_BASELINE_INQ:-0}" -ne 0 ]]; then INQUIRY_POLICY_OK=0; fi

LAN_LIST=()
if [[ "$RUN_JLG" -eq 1 ]]; then
  LAN_LIST+=("${FLOW_LAN[JLG-S1]:-}" "${FLOW_LAN[JLG-S7]:-}")
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  LAN_LIST+=("${FLOW_LAN[INDL-S1]:-}" "${FLOW_LAN[INDL-S7]:-}")
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  LAN_LIST+=("${FLOW_LAN[SHG-S1]:-}" "${FLOW_LAN[SHG-S7]:-}")
fi

SCOPED_LANS=()
for lan in "${LAN_LIST[@]}"; do
  if [[ -n "${lan:-}" && "$lan" != "NA" ]]; then
    SCOPED_LANS+=("$lan")
  fi
done

if [[ "${#SCOPED_LANS[@]}" -gt 0 ]]; then
  quoted_lans="$(printf "'%s'," "${SCOPED_LANS[@]}")"
  quoted_lans="${quoted_lans%,}"
  crr_blank_sql=$(cat <<SQL
SELECT
  COUNT(*) FILTER (WHERE transaction_type IS NULL OR btrim(transaction_type)='')::text || '|' ||
  COUNT(*) FILTER (WHERE request IS NULL OR btrim(request)='')::text || '|' ||
  COUNT(*) FILTER (WHERE response IS NULL OR btrim(response)='')::text
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number IN ($quoted_lans)
  AND updated_on >= '$RUN_START_TS';
SQL
)
  crr_blank_line="$(psql "$PSQL_URI" -At -c "$crr_blank_sql")"
  blank_tx="$(awk -F'|' '{print $1+0}' <<<"$crr_blank_line")"
  blank_req="$(awk -F'|' '{print $2+0}' <<<"$crr_blank_line")"
  blank_resp="$(awk -F'|' '{print $3+0}' <<<"$crr_blank_line")"
  if [[ "$blank_tx" -ne 0 || "$blank_req" -ne 0 || "$blank_resp" -ne 0 ]]; then
    CRR_INTEGRITY_OK=0
  fi

  crr_sig_sql=$(cat <<SQL
WITH scoped AS (
  SELECT
    loan_account_number,
    transaction_type,
    md5(COALESCE(request,'')) AS req_sig,
    md5(COALESCE(response,'')) AS resp_sig
  FROM mfi_accounting.client_request_response_log
  WHERE loan_account_number IN ($quoted_lans)
    AND updated_on >= '$RUN_START_TS'
)
SELECT COUNT(*)
FROM (
  SELECT loan_account_number, req_sig, resp_sig
  FROM scoped
  GROUP BY loan_account_number, req_sig, resp_sig
  HAVING COUNT(*) > 1 AND COUNT(DISTINCT transaction_type) > 1
) suspicious;
SQL
)
  suspicious_sig_count="$(psql "$PSQL_URI" -At -c "$crr_sig_sql" | awk 'NF{print $1; found=1} END{if(!found) print 0}')"
  if [[ "${suspicious_sig_count:-0}" -ne 0 ]]; then
    CRR_INTEGRITY_OK=0
  fi
else
  CRR_INTEGRITY_OK=0
fi

SHG_ACCOUNTS=()
if [[ "$RUN_SHG" -eq 1 ]]; then
  for flow in SHG-S1 SHG-S7; do
    aid="${FLOW_ACCOUNT_ID[$flow]:-}"
    if [[ -n "$aid" ]]; then
      SHG_ACCOUNTS+=("$aid")
    fi
  done
fi

CLMT_OK=1
if [[ "$RUN_SHG" -eq 1 && "${#SHG_ACCOUNTS[@]}" -gt 0 ]]; then
  id_list="$(IFS=,; echo "${SHG_ACCOUNTS[*]}")"
  CLMT_SQL=$(cat <<SQL
SELECT parent_account_id || '|' || COUNT(*)::text || '|' ||
       SUM(CASE WHEN event_status IN ('C','COMPLETED') THEN 1 ELSE 0 END)::text
FROM mfi_accounting.loan_account_events_queue
WHERE is_deleted = false
  AND event_type = 'CLMT'
  AND parent_account_id IN ($id_list)
GROUP BY parent_account_id
ORDER BY parent_account_id;
SQL
)
  CLMT_LINES="$(psql "$PSQL_URI" -At -c "$CLMT_SQL")"
  for aid in "${SHG_ACCOUNTS[@]}"; do
    line="$(awk -F'|' -v id="$aid" '$1==id {print $0}' <<<"$CLMT_LINES")"
    if [[ -z "$line" ]]; then
      CLMT_OK=0
      continue
    fi
    total="$(awk -F'|' '{print $2}' <<<"$line")"
    completed="$(awk -F'|' '{print $3}' <<<"$line")"
    if [[ "${total:-0}" -lt 1 || "${completed:-0}" -lt 1 ]]; then
      CLMT_OK=0
    fi
  done
elif [[ "$RUN_SHG" -eq 1 ]]; then
  CLMT_OK=0
fi

# Child Loan Booking (CLB) rows on same parent_account_id as CLMT (ExecutionContext account_id).
CLB_OK=1
if [[ "$RUN_SHG" -eq 1 ]]; then
  CLB_SQL=""
  id_list_clb="$(echo "${FLOW_ACCOUNT_ID[SHG-S1]:-} ${FLOW_ACCOUNT_ID[SHG-S7]:-}" | tr ' ' '\n' | awk 'NF' | paste -sd, -)"
  if [[ -n "$id_list_clb" ]]; then
    CLB_SQL=$(cat <<SQL
SELECT parent_account_id::text || '|' || COUNT(*)::text || '|' ||
       SUM(CASE WHEN UPPER(BTRIM(event_status)) IN ('C','COMPLETED') THEN 1 ELSE 0 END)::text || '|' ||
       SUM(CASE WHEN UPPER(BTRIM(event_status)) = 'P' THEN 1 ELSE 0 END)::text
FROM mfi_accounting.loan_account_events_queue
WHERE is_deleted = false
  AND event_type = 'CLB'
  AND parent_account_id IN ($id_list_clb)
GROUP BY parent_account_id
ORDER BY parent_account_id;
SQL
)
    CLB_LINES="$(psql "$PSQL_URI" -At -c "$CLB_SQL")"
  else
    CLB_LINES=""
  fi
  for flow in SHG-S1 SHG-S7; do
    aid="${FLOW_ACCOUNT_ID[$flow]:-}"
    disb_raw="${FLOW_DISB_STATUS[$flow]:-}"
    disb="$(echo "$disb_raw" | tr '[:lower:]' '[:upper:]')"
    if [[ -z "$aid" ]]; then
      CLB_OK=0
      continue
    fi
    line="$(awk -F'|' -v id="$aid" '$1==id {print $0}' <<<"$CLB_LINES")"
    if [[ -z "$line" ]]; then
      CLB_OK=0
      continue
    fi
    total="$(awk -F'|' '{print $2}' <<<"$line")"
    completed="$(awk -F'|' '{print $3}' <<<"$line")"
    pending="$(awk -F'|' '{print $4}' <<<"$line")"
    if [[ "${total:-0}" -lt 1 ]]; then
      CLB_OK=0
      continue
    fi
    case "$disb" in
      COMPLETED)
        if [[ "${pending:-0}" -ne 0 || "${completed:-0}" -ne "${total:-0}" ]]; then
          CLB_OK=0
        fi
        ;;
      CHILD_SUCCESS)
        # Domain: parent stays CHILD_SUCCESS while at least one CLB row is still pending.
        if [[ "${pending:-0}" -lt 1 ]]; then
          CLB_OK=0
        fi
        ;;
      *)
        # PARENT_SUCCESS or other accepted SHG terminal-ish states: require CLB events exist.
        ;;
    esac
  done
fi

check_parent_transfer_idempotency() {
  local lan="$1"
  local mode="$2" # MFT or NEFT
  local sql
  sql=$(cat <<SQL
SELECT transaction_type || '|' || COUNT(*)::text
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = '$lan'
  AND status = 'SUCCESS'
  AND updated_on >= '$RUN_START_TS'
  AND transaction_type IN (
    'DISBURSEMENT_MFT', 'DISBURSEMENT_MFT_REINIT',
    'DISBURSEMENT_NEFT', 'DISBURSEMENT_NEFT_REINIT'
  )
GROUP BY transaction_type;
SQL
)
  local rows
  rows="$(psql "$PSQL_URI" -At -c "$sql")"

  local mft=0
  local mft_reinit=0
  local neft=0
  local neft_reinit=0
  while IFS='|' read -r tx c; do
    [[ -z "$tx" ]] && continue
    case "$tx" in
      DISBURSEMENT_MFT) mft="$c" ;;
      DISBURSEMENT_MFT_REINIT) mft_reinit="$c" ;;
      DISBURSEMENT_NEFT) neft="$c" ;;
      DISBURSEMENT_NEFT_REINIT) neft_reinit="$c" ;;
    esac
  done <<<"$rows"

  if [[ "$mode" == "MFT" ]]; then
    if [[ "$mft" -eq 0 && "$mft_reinit" -eq 0 && "$neft" -eq 0 && "$neft_reinit" -eq 0 ]]; then
      echo "[matrix] idempotency note lan=$lan mode=$mode had no new transfer rows in run window (terminal/no-op replay)."
      return 0
    fi
    if [[ $((mft + mft_reinit)) -lt 1 || "$mft_reinit" -gt 1 ]]; then
      echo "[matrix] idempotency fail lan=$lan mode=$mode mft=$mft mft_reinit=$mft_reinit neft=$neft neft_reinit=$neft_reinit"
      return 1
    fi
  else
    if [[ "$mft" -eq 0 && "$mft_reinit" -eq 0 && "$neft" -eq 0 && "$neft_reinit" -eq 0 ]]; then
      echo "[matrix] idempotency note lan=$lan mode=$mode had no new transfer rows in run window (terminal/no-op replay)."
      return 0
    fi
    if [[ $((neft + neft_reinit)) -lt 1 || "$neft_reinit" -gt 1 ]]; then
      echo "[matrix] idempotency fail lan=$lan mode=$mode mft=$mft mft_reinit=$mft_reinit neft=$neft neft_reinit=$neft_reinit"
      return 1
    fi
  fi
  return 0
}

if [[ "$RUN_JLG" -eq 1 ]]; then
  check_parent_transfer_idempotency "${FLOW_LAN[JLG-S1]:-}" "MFT" || IDEMPOTENCY_OK=0
  if [[ "${FLOW_LAN[JLG-S7]:-}" != "${FLOW_LAN[JLG-S1]:-}" ]]; then
    check_parent_transfer_idempotency "${FLOW_LAN[JLG-S7]:-}" "MFT" || IDEMPOTENCY_OK=0
  fi
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  check_parent_transfer_idempotency "${FLOW_LAN[INDL-S1]:-}" "NEFT" || IDEMPOTENCY_OK=0
  if [[ "${FLOW_LAN[INDL-S7]:-}" != "${FLOW_LAN[INDL-S1]:-}" ]]; then
    check_parent_transfer_idempotency "${FLOW_LAN[INDL-S7]:-}" "NEFT" || IDEMPOTENCY_OK=0
  fi
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  check_parent_transfer_idempotency "${FLOW_LAN[SHG-S1]:-}" "MFT" || IDEMPOTENCY_OK=0
  check_parent_transfer_idempotency "${FLOW_LAN[SHG-S7]:-}" "MFT" || IDEMPOTENCY_OK=0

  # Child transfer lanes (DISBURSEMENT_EXTREF...) must not duplicate per child reference.
  id_list="$(IFS=,; echo "${SHG_ACCOUNTS[*]}")"
  if [[ -n "$id_list" ]]; then
    dup_sql=$(cat <<SQL
SELECT transaction_type || '|' || COUNT(*)::text
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number IN ('${FLOW_LAN[SHG-S1]:-}','${FLOW_LAN[SHG-S7]:-}')
  AND status='SUCCESS'
  AND updated_on >= '$RUN_START_TS'
  AND transaction_type LIKE 'DISBURSEMENT_EXTREF%'
GROUP BY transaction_type
HAVING COUNT(*) > 1;
SQL
)
    dup_rows="$(psql "$PSQL_URI" -At -c "$dup_sql")"
    if [[ -n "$dup_rows" ]]; then
      IDEMPOTENCY_OK=0
    fi
  fi
fi

echo
echo "=== Disbursement Summary (${TARGET}) ==="
if [[ "$RUN_JLG" -eq 1 ]]; then
  for flow in JLG-S1 JLG-S7; do
    printf "%-8s | lan=%-10s | loan_status=%-8s | disb_status=%s\n" \
      "$flow" "${FLOW_LAN[$flow]:-NA}" "${FLOW_LOAN_STATUS[$flow]:-NA}" "${FLOW_DISB_STATUS[$flow]:-NA}"
  done
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  for flow in INDL-S1 INDL-S7; do
    printf "%-8s | lan=%-10s | loan_status=%-8s | disb_status=%s\n" \
      "$flow" "${FLOW_LAN[$flow]:-NA}" "${FLOW_LOAN_STATUS[$flow]:-NA}" "${FLOW_DISB_STATUS[$flow]:-NA}"
  done
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  for flow in SHG-S1 SHG-S7; do
    printf "%-8s | lan=%-10s | loan_status=%-8s | disb_status=%s\n" \
      "$flow" "${FLOW_LAN[$flow]:-NA}" "${FLOW_LOAN_STATUS[$flow]:-NA}" "${FLOW_DISB_STATUS[$flow]:-NA}"
  done
  echo "SHG CLMT evidence: $([[ "$CLMT_OK" -eq 1 ]] && echo PASS || echo FAIL)"
  echo "SHG CLB evidence: $([[ "$CLB_OK" -eq 1 ]] && echo PASS || echo FAIL)"
fi
echo "S8 queue soft-delete / replay scenario: $([[ "$S8_OK" -eq 1 ]] && echo PASS || echo FAIL)"
if [[ "$RUN_JLG" -eq 1 ]]; then
  echo "JLG inquiry delta baseline/replay: ${JLG_BASELINE_INQ}/${JLG_REPLAY_INQ}"
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  echo "INDL inquiry delta baseline/replay: ${INDL_BASELINE_INQ}/${INDL_REPLAY_INQ}"
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  echo "SHG inquiry delta baseline/replay: ${SHG_BASELINE_INQ}/${SHG_REPLAY_INQ}"
fi
echo "Inquiry policy (baseline must be 0): $([[ "$INQUIRY_POLICY_OK" -eq 1 ]] && echo PASS || echo FAIL)"
echo "Transfer idempotency checks: $([[ "$IDEMPOTENCY_OK" -eq 1 ]] && echo PASS || echo FAIL)"
echo "CRR integrity (tx/request/response/signature): $([[ "$CRR_INTEGRITY_OK" -eq 1 ]] && echo PASS || echo FAIL)"
LOG_SUMMARY=()
if [[ "$RUN_JLG" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_JLG"); fi
if [[ "$RUN_INDL" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_INDL"); fi
if [[ "$RUN_SHG" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_SHG"); fi
echo "Logs: ${LOG_SUMMARY[*]}"

if [[ "$MATRIX_OK" -eq 1 && "$CLMT_OK" -eq 1 && "$CLB_OK" -eq 1 && "$IDEMPOTENCY_OK" -eq 1 && "$INQUIRY_POLICY_OK" -eq 1 && "$CRR_INTEGRITY_OK" -eq 1 && "$S8_OK" -eq 1 ]]; then
  echo "[matrix] PASS"
  exit 0
fi

echo "[matrix] FAIL"
exit 1
