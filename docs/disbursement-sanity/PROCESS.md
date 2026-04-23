# Disbursement Testing Process (Local)

Scope: local accounting validation with simulator-backed bank responses and DB proof.

Shortcut wrapper (runs JLG + INDL + SHG matrix and prints DB-backed PASS/FAIL summary):

```bash
/home/darpan/Documents/sliProd/scripts/run_disbursement_full_matrix.sh
```

Single-product demo run:

```bash
/home/darpan/Documents/sliProd/scripts/run_disbursement_full_matrix.sh JLG
/home/darpan/Documents/sliProd/scripts/run_disbursement_full_matrix.sh INDL
/home/darpan/Documents/sliProd/scripts/run_disbursement_full_matrix.sh SHG
```

## 1) Preconditions

- Accounting service running on `http://localhost:8002/accounting`
- Simulator service running on `http://localhost:8018`
- Kafka running on `localhost:9092` (required for async-heavy paths)
- Yugabyte reachable (`host=localhost`, `port=5433`, `db=yugabyte`, schema `mfi_accounting`)

Quick check:

```bash
curl -s http://localhost:8002/accounting/actuator/health
curl -s http://localhost:8018/simulate/getAllResponses
ss -ltn | awk '/:9092 / {print}'
```

## 2) One command to run suite

Minimal:

```bash
rm -f /tmp/disburse_loan_sanity.lock
python3 scripts/disburse_loan_sanity.py \
  --request-file scripts/disburse_loan_sanity_request_4495972134234554346565.json \
  --stage-suite minimal \
  --simulator-profile success \
  --reset-before \
  --reset-target-disb-status LAN_CREATED \
  --http-timeout-s 30 \
  --wait-timeout-s 120 \
  --poll-s 2.0
```

Full:

```bash
rm -f /tmp/disburse_loan_sanity.lock
python3 scripts/disburse_loan_sanity.py \
  --request-file scripts/disburse_loan_sanity_request_4495972134234554346565.json \
  --stage-suite full \
  --simulator-profile success \
  --reset-before \
  --reset-target-disb-status LAN_CREATED \
  --http-timeout-s 30 \
  --wait-timeout-s 180 \
  --poll-s 2.0
```

Kafka-entry full flavours (normal/replay/reinit/stage/fresh-second-ref) matrix:

```bash
cd /home/darpan/Documents/sliProd/novopay-platform-accounting-v2
CP=$(./gradlew -q --init-script tmp-printcp.init.gradle printTestRuntimeClasspath)
```

JLG (`product_id=2`, ACCTWB required in local DB):

```bash
KAFKA_ENTRY_TEST_CUSTOMER_ID=10002173 \
KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID=10002197 \
KAFKA_ENTRY_FORCE_DISBURSEMENT_MODE=ACCTWB \
KAFKA_ENTRY_SCENARIO_START=1 \
KAFKA_ENTRY_SCENARIO_LIMIT=7 \
java -cp "$CP" in.novopay.accounting.consumers.LmsDisburseKafkaEntryFlowRunner \
  /home/darpan/Documents/sliProd/scripts/disburse_loan_sanity_request_4495972134234554346565.json
```

INDL (`product_id=45`, NEFT v1 payload):

```bash
KAFKA_ENTRY_TEST_CUSTOMER_ID=10002221 \
KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID=10002215 \
KAFKA_ENTRY_SCENARIO_START=1 \
KAFKA_ENTRY_SCENARIO_LIMIT=7 \
java -cp "$CP" in.novopay.accounting.consumers.LmsDisburseKafkaEntryFlowRunner \
  /home/darpan/Documents/sliProd/scripts/disburse_loan_sanity_request_370164.json
```

SHG (`product_id=44`, parent + child with CLMT evidence):

```bash
KAFKA_ENTRY_TEST_CUSTOMER_ID=10002185 \
KAFKA_ENTRY_TEST_SECONDARY_CUSTOMER_ID=10002179 \
KAFKA_ENTRY_SCENARIO_START=1 \
KAFKA_ENTRY_SCENARIO_LIMIT=7 \
java -cp "$CP" in.novopay.accounting.consumers.LmsDisburseKafkaEntryFlowRunner \
  /home/darpan/Documents/sliProd/scripts/disburse_loan_sanity_request_shg_41333333.json
```

Customer picker SQL (recommended before every run; run per product id):

```sql
WITH p AS (SELECT id FROM mfi_accounting.loan_product WHERE product_id = :product_id LIMIT 1)
SELECT c.id
FROM mfi_actor.customer c
LEFT JOIN mfi_accounting.loan_account la
  ON la.customer_id = c.id
 AND la.loan_product_id = (SELECT id FROM p)
 AND la.loan_status = 'ACTIVE'
 AND la.is_deleted = false
WHERE c.status = 'ACTIVE'
  AND c.is_deleted = false
  AND la.account_id IS NULL
ORDER BY c.id DESC
LIMIT 20;
```

## 3) Mandatory validation evidence

For each scenario, collect both:

1. Loan state movement from `loan_account`
2. External-call evidence from `client_request_response_log` (CRR)

SQL template:

```sql
SELECT la.account_id, a.account_number, la.external_ref_number, la.loan_status, la.disbursement_status, la.updated_on
FROM mfi_accounting.loan_account la
JOIN mfi_accounting.account a ON a.id = la.account_id
WHERE a.account_number = :lan;

SELECT transaction_type, status, count(*) AS rows, max(system_date) AS latest
FROM mfi_accounting.client_request_response_log
WHERE loan_account_number = :lan
GROUP BY transaction_type, status
ORDER BY latest DESC;
```

## 4) Pass criteria

- Status progression reaches expected terminal state for scenario
- CRR rows appear for required bank/GL legs
- Replay scenarios do not create unexpected duplicate non-archived CRR rows
- SHG: `loan_account_events_queue` contains `CLMT` rows for the parent account and they progress to completed states

## 5) Blocker signature (do not mark pass)

If API returns success but all three happen:

- `disbursement_status` stays at `LAN_CREATED`
- CRR stays empty for live rows
- no bank-leg transaction types appear

then this is an environment/runtime flow blocker, not a passed disbursement flow.

## 6) Useful paths

- Accounting logs: `/home/darpan/Documents/sliProdLogs/mfi/accounting-mfi.log`
- Suite reports: `docs/disbursement-sanity/`
- Reset recipes: `docs/disbursement-reset-recipes/`

## 7) Git hygiene for local runs

- Do not stage/push local/system files from test execution (example: `tmp-printcp.init.gradle`, local log tails, lock files, ad-hoc temp payloads).
- Before commit, verify using `git status --short` from the module and unstage any system artifact immediately.
