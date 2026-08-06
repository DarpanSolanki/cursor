---
name: feedback-kafka-disburse-local-harness-gotchas
description: Two local-only traps that make Kafka-entry disburse tests look hung; neither is a product defect
metadata:
  type: feedback
---

Found while proving SDCP-11294 (2026-08-06). Both cost multiple wasted runs and both look
identical to "the product is broken" or "the agent is stuck".

## 1. `agent-ops` reports the disburse consumer assigned when it is not

`kafka: consumer assigned (0s)` is satisfied by the consumer **group existing** with committed
offsets. A group whose member count is zero still answers "assigned", so a run proceeds while
nothing is consumed — every scenario then times out and the topic offset never moves.

**Check for a live member, not a live group:**

```bash
kafka-consumer-groups.sh --bootstrap-server 127.0.0.1:9092 \
  --describe --group disburse_loan_api_consumer_mfi_local
# CONSUMER-ID column must not be "-"
```

Match the group name in column 0 — the header row's 7th column is the literal string
`CONSUMER-ID`, so a naive "column 7 is non-empty" test passes on the header and reintroduces
the false positive.

Fix: `bash scripts/bin/novopay-service.sh restart accounting`, then wait for a real CONSUMER-ID.

## 2. A fixture reset fired mid-disburse wedges the consumer on a row lock

Bulk `UPDATE loan_account/account` for the customers the in-flight disburse is still writing
causes Yugabyte row-lock contention. The consumer thread blocks inside
`PgPreparedStatement.executeUpdate`, stops polling, and the coordinator evicts it — so the
symptom is "consumer detaches after ~4 messages", not a visible error.

Confirm with `jstack <accounting-pid>`: look for a thread RUNNABLE in
`sun.nio.ch.Net.poll` under `NativeQueryImpl.doExecuteUpdate`.

**Drain before resetting** — wait for the disburse consumer group to reach lag 0, then reset.
Implemented as `wait_consumer_idle()` in
`scripts/testing/disbursement/sync_error_message_placeholder.py`.

## 3. Reset per scenario, not once per run

Each disburse leaves an ACTIVE loan, so the next scenario for the same customer dies on
**134494** (active loan for this product) before reaching the validation under test. Without a
per-scenario reset the matrix silently degrades into codes that prove nothing.

## Speed

`kafka-console-consumer.sh` without `--max-messages` sits out the whole `--timeout-ms` even when
the record arrived immediately — 60s per scenario instead of ~4s. Always pass `--max-messages`
when reading a known number of records.

Related: [[feedback_ship_test_autonomy_change_map]], [[reference_dpi_feature_branch]]
