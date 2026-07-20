---
name: autonomous-workspace-ops
description: >-
  Autonomous sliProd ops: when to auto-run agent-ops.sh, novopay-service.sh,
  novopay-logs.sh, dpi-sanity, ntest ensure. Use at session start, before tests,
  on failure, or when user asks for sanity.
---

# Autonomous workspace ops

Read `.cursor/rules/autonomous-workspace-ops.mdc` and `.cursor/workspace-ops-state.md`.

**Single entry:** `bash scripts/bin/agent-ops.sh before-test <apiName>` before any batch/DPI test.

**Never** skip ensure/sanity because a port is down. **Never** wait blind — `novopay-logs.sh snap`.

For local `disburseLoan`, also require the bank simulator on `localhost:8018` and use
`ntest run disbursement.indl`. Its reset fixture derives the request `REP_ACCT`, creates
`repayment_account_details`, links the active/pending mandate, and fails before the API call
if the mandate CASA is missing or mismatched.

**Mandate verify (local DB):**
```bash
bash scripts/db-local.sh --sql "SELECT rmd.id, rmd.mandate_status, rad.account_number
FROM mfi_accounting.repayment_mandate_details rmd
JOIN mfi_accounting.repayment_account_details rad ON rad.id = rmd.repayment_account_details_id
WHERE rmd.loan_application_id = '370164' AND rmd.is_deleted = false;"
```

**Kafka consumer (Accounting):** topic `disburse_loan_api_mfi_local`, group
`disburse_loan_api_consumer_mfi_local`. Confirm with
`kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group disburse_loan_api_consumer_mfi_local`.

**Redis locks (TDPQA-54):** ACCOUNTING Redis DB `5`, key shape `localmfi_<key>` /
`localmfi_dl<key>`, TTL default `600000ms`. Direct Accounting HTTP does **not** take these
locks; produce to `disburse_loan_api_mfi_local` (or LOS `triggerDisburseLoan`) and poll
`redis-cli -n 5 PTTL localmfi_dl…`. Suite sim: `ntest run disbursement.redis_inflight_lock_sim`.

## Disburse / money API Pass bar (mandatory column audit)

Never claim Pass on `disburseLoan` / money APIs from HTTP 200 or row presence alone.

1. Drive the **real** API/batch (`disburse-any-quick.sh` / `ntest run disbursement.{indl,jlg,shg,any}`).
2. Suite runs `disbursement_suite.column_audit.audit_disbursement` — FAIL on wrong
   `loan_account` / installments / dues / mode / LDT / TM / CRR column values.
3. Registry cases must declare `acceptance.db_asserts` covering
   `domain_money_tables.disbursement` in `acceptance_coverage_manifest.json`.
4. SHG needs member `REP_ACCT` + suite-driven `childLoanEventProcessingBatchJob`; schedule
   asserts are on **children**, not parent.

Memory: `feedback_real_flow_db_write_validate.md`, `feedback_disburse_column_audit_mandatory.md`.
