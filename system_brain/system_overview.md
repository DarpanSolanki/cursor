# System Brain Overview (code-verified where noted)

This directory stores persistent, reusable system intelligence for the Lending + Accounting platform in `sliProd`.

**Workspace-wide map (services ↔ Kafka ↔ Redis ↔ money paths):** `.cursor/knowledge-graph.md` (Flow Sync). Use it with this brain: **graph** = hops and contract status; **`system_brain/flows/`** = step-by-step behaviour.

## Money-posting spine (ledger write model)
The core ledger write path converges on the `postTransaction` orchestration request (accounting-v2) which:
1. Validates and prepares transaction inputs (ExecutionContext).
2. Resolves placeholders (`account_details[]`, internal account definitions, GL mapping).
3. Executes transaction rules to produce debit/credit component partitions and rollups.
4. Persists ledger artifacts (`transaction_master`, `transaction_partition_details`, `transaction_details`).

### Debit/Credit sign mapping (code-verified)
`in.novopay.accounting.transaction.processor.CreateTransactionDetailsProcessor` sets:
- `cr_dr_indicator = CrDrIndicator.C` when `netAmount > 0`
- `cr_dr_indicator = CrDrIndicator.D` when `netAmount < 0`
- skips row creation when `netAmount == 0`
and persists `transaction_details` with `netAmount = abs(netAmount)`.

## Disbursement: end-to-end idempotency + sync contract

### Kafka request payload + Redis in-flight lock
Verified in code:
1. LOS producer builds and sends `disburseLoan|<request_json>|<cacheKey>` where
   `cacheKey = "disburseLoan" + <productId_defaultString> + "_" + <externalRef_defaultString>`.
2. Producer writes a Redis marker without TTL:
   `novopayCacheClient.set(tenant, cacheKey, "in_progress", RedisDBConfig.ACCOUNTING)`
3. Accounting consumer parses the last pipe segment as `originalCacheKey` and uses a lock key:
   `dl + originalCacheKey`
4. Consumer publishes a sync result to Kafka topic `los_lms_disbursement_sync`.

### Disbursement sync `entity_type` is mandatory (code-verified)
- `in.novopay.los.service.disbursement.DisbursementSyncService` reads `entity_type` from ExecutionContext.
- If `entity_type` is blank/missing it returns early (“entityType is null”) and does not update `disburse_loan_process`.

## Redis cache semantics (code-verified)
1. Redis keys are tenant-scoped via: `<environment_prefix_if_present><tenantCode>_<key>`.
2. `getKeysWithMatchingPrefix(...)` actually calls `flushDb()` per Redis DB index (broad eviction, not prefix-based).

## What to do when debugging (rule of thumb)
- Start from a concrete trigger (API/Kafka/batch).
- Trace to the ledger write or sync handler.
- Verify message contracts (Kafka payload mandatory keys) and Redis lock semantics before assuming DB state issues.

## Confidence
- High: ledger posting engine convergence (`postTransaction`) + debit/credit sign mapping; disbursement Kafka payload format + Redis in-flight lock semantics; disbursement sync no-op when `entity_type` missing.
- High: non-batch posting entrypoints in accounting-v2 ORC (repayment, prepayment/foreclosure, writeoff, excess refund, rebooking, disbursement cancellation) are wired to `postTransaction` in orchestration XMLs.
- High: Death foreclosure insurance inbound -> batch processing -> `DeathForeclosureInsuranceWriter` -> `postTransaction` (`transaction_type=DEATH_FORECLOSURE` and `RSCH_DEATH_FORECLOSURE`).
- High: Disbursement cancellation insurance inbound -> `bulkSGToDisbursementCancellationJob` -> `SGToDisbursementCancellationIWriter` -> `postTransaction` (`transaction_type=LOAN_DISB_CNCL`) + `InitiateCancellationTaxReversalProcessor`.
- High: Post-disbursement insurance inbound -> `bulkSGToPostDisbursementInsuranceUpdateJob` only updates insurance statuses and generates provider files (no `postTransaction` call in this chain).

