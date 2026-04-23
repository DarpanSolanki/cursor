#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ACCOUNTING_DIR="$ROOT_DIR/novopay-platform-accounting-v2"
RUNNER_CLASS="in.novopay.accounting.consumers.LmsDisburseKafkaEntryFlowRunner"
TMP_DIR="${TMPDIR:-/tmp}/disbursement_full_matrix"
mkdir -p "$TMP_DIR"

# DB connection can be overridden if needed.
PSQL_URI="${PSQL_URI:-host=127.0.0.1 port=5433 dbname=yugabyte user=yugabyte password=yugabyte}"

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
    KAFKA_ENTRY_SCENARIO_LIMIT=7 \
    "$@" \
    java -cp "$CP" "$RUNNER_CLASS" "$payload" >"$log_file" 2>&1

  local start_count
  local end_count
  start_count="$(awk '/\[kafka-entry\] start scenario=/{c++} END{print c+0}' "$log_file")"
  end_count="$(awk '/\[kafka-entry\] end scenario=/{c++} END{print c+0}' "$log_file")"

  if [[ "$start_count" -ne 7 || "$end_count" -ne 7 ]]; then
    echo "[matrix] ${label}: FAILED (expected 7 scenario starts/ends, got starts=${start_count}, ends=${end_count})"
    echo "[matrix] Check log: $log_file"
    return 1
  fi

  if awk '/Fatal error while processing LMS disbursement|NumberFormatException|NovopayFatalException:/{found=1} END{exit found?0:1}' "$log_file"; then
    echo "[matrix] ${label}: FAILED (fatal signature found in log)"
    echo "[matrix] Check log: $log_file"
    return 1
  fi

  echo "[matrix] ${label}: runner scenarios completed"
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

if [[ "$RUN_JLG" -eq 1 ]]; then
  run_suite "JLG" "$JLG_PAYLOAD" "$LOG_JLG" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$JLG_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$JLG_SECONDARY" \
    KAFKA_ENTRY_FORCE_DISBURSEMENT_MODE="ACCTWB"
  JLG_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_JLG")"
  JLG_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_JLG")"
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  run_suite "INDL" "$INDL_PAYLOAD" "$LOG_INDL" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$INDL_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$INDL_SECONDARY"
  INDL_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_INDL")"
  INDL_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_INDL")"
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  run_suite "SHG" "$SHG_PAYLOAD" "$LOG_SHG" \
    KAFKA_ENTRY_TEST_CUSTOMER_ID="$SHG_PRIMARY" \
    KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID="$SHG_SECONDARY"
  SHG_S1_EXTREF="$(extract_ext_ref "S1_default_once" "$LOG_SHG")"
  SHG_S7_EXTREF="$(extract_ext_ref "S7_fresh_second_ref" "$LOG_SHG")"
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

if [[ "$RUN_JLG" -eq 1 ]]; then
  if ! check_flow_state "JLG-S1" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
  if ! check_flow_state "JLG-S7" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
fi
if [[ "$RUN_INDL" -eq 1 ]]; then
  if ! check_flow_state "INDL-S1" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
  if ! check_flow_state "INDL-S7" "ACTIVE" "COMPLETED"; then MATRIX_OK=0; fi
fi
if [[ "$RUN_SHG" -eq 1 ]]; then
  if ! check_flow_state "SHG-S1" "ACTIVE" "PARENT_SUCCESS"; then MATRIX_OK=0; fi
  if ! check_flow_state "SHG-S7" "ACTIVE" "PARENT_SUCCESS"; then MATRIX_OK=0; fi
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
fi
LOG_SUMMARY=()
if [[ "$RUN_JLG" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_JLG"); fi
if [[ "$RUN_INDL" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_INDL"); fi
if [[ "$RUN_SHG" -eq 1 ]]; then LOG_SUMMARY+=("$LOG_SHG"); fi
echo "Logs: ${LOG_SUMMARY[*]}"

if [[ "$MATRIX_OK" -eq 1 && "$CLMT_OK" -eq 1 ]]; then
  echo "[matrix] PASS"
  exit 0
fi

echo "[matrix] FAIL"
exit 1
