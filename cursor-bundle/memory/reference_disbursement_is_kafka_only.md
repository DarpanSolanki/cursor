---
name: reference-disbursement-is-kafka-only
description: Disbursement runs only over Kafka; the ALREADY_ACTIVE replay guard is correctly Kafka-only — do not re-raise as a duplicate-disbursement gap
metadata:
  type: reference
---

Confirmed by Darpan, 2026-08-06.

**LOS disburses only by producing to `disburse_loan_api_*`.** There is no HTTP
disbursement caller. So the replay/dedupe guard living solely in
`LmsMessageBrokerConsumer.getDisburseDecision` (`ALREADY_ACTIVE` / `LOCK_LOAN_STATUS` /
`FAIL_CLOSED`) sits on the only entry point that needs it. That placement is deliberate.

## What you will observe, and why it is not a bug

A direct HTTP `POST /accounting/api/v1/disburseLoan` replay against a **COMPLETED**
NEFTv2 loan re-fires `ST_NEF` and walks `disbursement_status` back to
`NEFT_STAGE_1_PENDING` (seen on LAN 6004192325: `DISBURSEMENT_NEFT_NEF` 1 -> 2). The HTTP
path never passes through the consumer, so nothing suppresses it.

**Do not** report this as the 3x-NEFT duplicate class, and do not "fix" it by asserting
suppression on the HTTP entry — that tests a guard the entry point does not have.
`disbursement.indl` therefore reports `crr_success_not_increased_NEFT` / `utr_stable` as a
WARN carrying the reason, and asserts them for real on the Kafka entry
(`disburse-indl-kafka-quick.sh` / `--via-kafka`), where the replay yields
`neft_success_delta=0`.

## The one condition that changes this

If an HTTP disburse caller is ever introduced, the guard must move into the `disburseLoan`
orchestration **before** that caller ships — otherwise it becomes a genuine
duplicate-disbursement path.

Related: [[feedback_kafka_disburse_local_harness_gotchas]]
