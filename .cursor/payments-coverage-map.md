# Payments coverage — what is proven, beyond the health probe

Scope: `trustt-platform-payments`. Measured 2026-08-08 against local checkout
`mfi_integration_v3.4.2.5` (`d833bb860`). Same convention as
`.cursor/accounting-coverage-map.md` — read that document's Grading/Dead-code sections for the
shared method; this file states payments-specific numbers only.

**Everything here runs correctly in production.** A flow listed uncovered is a gap in *this test
suite*, not a product defect. Read the whole document with that prior.

## Headline

**1 of 275 live payments apiNames (0.4%) has any registry case at all, and that one case has no
declared `verify_mode`** (`foreclosure.cancel_collections`, `expect: {status, code}` — a JTF
envelope check, not a value assert). **0 of 275 are runtime-verified.**

`health.payments` (`smoke` tier, probes `getCollectionList`) is the only other payments-tagged
registry entry — a liveness probe, not an API/flow case.

Payments has no domain-coverage script analogous to `accounting-flow-coverage.sh` and no
`accounting_flow_domains.json` equivalent — this map is the first version of that view for this
service.

---

## 1. Payments apiName inventory

```
python3 scripts/testing/platform_api_map.py --api <name>
```

| | |
|---|---|
| accounting APIs (for scale reference) | 363 |
| **payments APIs total** (`cursor-bundle/flow-test/platform_api_map.jsonl`, `repo == trustt-platform-payments`) | **275** |
| shaped as batch/job (`*Batch`, `*Job` in the apiName) | 66 |
| registry cases referencing a payments `api`/`apis` field (exact match, never case id) | **1** — `foreclosure.cancel_collections` |
| health-only entries | 1 — `health.payments` |
| `verify_mode: runtime` | **0** |
| `verify_mode` declared at all (sim/theatre/etc.) | **0** — the one case has no `verify_mode` key |
| **UNCOVERED** (no case, or case with no verify_mode) | **274 of 275 (99.6%)** |

Matched on the registry case's `api` field and `apis` list, never the case id, per
`40-knowledge-upkeep.md` convention (a name-only match once produced a duplicate case).
Verified two ways: `service == "payments"` filter (2 hits: `health.payments`,
`foreclosure.cancel_collections`) and an exact-quoted-literal scan of all 275 apiNames against
`scripts/testing/registry.json` text (1 hit: `"cancelCollections"`) — both agree.

**No domain breakdown exists yet** (accounting has `read_inquiry` / `write_ops` / `batch_other` /
`other` from `scripts/lib/accounting_flow_domains.json`; payments has no equivalent file). Building
one is this report's top recommendation — see §4.

---

## 2. Payments as a contract boundary

### 2.0 Methodology — why the generated `called_by` field is not enough

`cursor-bundle/flow-test/platform_api_map.jsonl`'s `called_by` derives from orchestration
`<Request>` nodes only. The accounting-side analysis
(`scripts/scratch/internal-caller-map/REPORT.md`) proved this undercounts cross-service Java
calls (`callInternalAPI`) by ~40%. The same check on payments:

```
python3 - <<'EOF'
# called_by field, filtered to callers outside trustt-platform-payments
python3 scripts/testing/platform_api_map.py --api <name>
EOF
```

- **Orchestration-declared cross-service callers** (`called_by`, caller repo ≠ payments): **12**
  payments apiNames.
- **Literal Java/XML scan** — every one of the 275 payments apiNames matched as a whole-word
  literal (`\bapiName\b`, not substring) across all other 14 repos'
  `*.java`/`*.xml`, then hand-classified per hit into `callInternalAPI(ctx, "name", ...)`,
  a bare quoted Java string `"name"`, an orchestration `<Request name="name">`, or "other"
  (log message / comment / same-named local method — excluded unless the same file also has a
  confirmed hit): **43** payments apiNames have at least one confirmed cross-service caller.
- **Result: orchestration `called_by` finds 12 of the 43 true cross-service callers — a 72%
  undercount**, the same class of miss as the accounting finding, and for the same reason
  (`callInternalAPI` from Java never appears as an orchestration `<Request>` node).

Three apiNames collide in name with an unrelated API in another repo
(`getIndividualCollectionDetails`/`getGroupCollectionDetails` vs `trustt-platform-actor`,
`updatePaymentStatus` vs `trustt-platform-api-gateway`) — checked individually; none produced a
false "payments has a caller" conclusion.

Command used:
```bash
rg -n -f payments_api_names.txt -F -g '*.java' -g '*.xml' \
  trustt-platform-accounting trustt-platform-actor trustt-platform-los trustt-platform-api-gateway \
  trustt-platform-approval trustt-platform-authorization trustt-platform-batch trustt-platform-bre \
  trustt-platform-dms trustt-platform-masterdata-management trustt-platform-notifications \
  trustt-platform-reporting trustt-platform-task trustt-platform-lib novopay-platform-lib
```
(275-name wordlist generated from `platform_api_map.jsonl` where `repo == trustt-platform-payments`.)

### 2.1 Confirmed cross-service caller ranking (43 apiNames)

`trustt-platform-actor` is payments' dominant caller by a wide margin — its whole
`custom/collections/**` package is built around calling payments internal APIs for collection
allocation, MIS reporting, and finnone bridging.

| Consuming service | payments APIs it calls | uncovered |
|---|---|---:|
| **trustt-platform-actor** | `fetchCollectionRecords`, `updateCollection`, `getCollectionMISReportDetails`, `getCollectionAttemptsReportDetails`, `getSettlementMISReportDetails`, `getIndividualCollectionDetails`, `getGroupCollectionDetails`, `updateCollectionCustomerInfo`, `getFinnoneCustomerDetailsByLAN`, `collectorCashInHand`, `getContactDetailsForFinnoneCustomer`, `updateCollectionOfficeInfo`, `updateScheduledBatchExpiryDate`, `fetchLMSUpdatesForCollections`, `getNearByCollectionDetails`, `getCollectionDetailsForCustomerInteractionList`, `getAgencyCode`, `getTraceCustomerReportDetails`, `createCollectionOfficeInfo`, `getCollectionsList`, `getCollectionTempData`, `getPriorityCollectionDetails`, `getCustomersIdSetForCollector`, `getUpdatedAmountOfCollection`, `validateLCSRestrictedActivitiesForPTrfr`, `createCollection`, `getFinnoneKeyMemberDetailsForGroup`, `getPastCollectionIdsForCollectionIds`, `getCollectorSummaryList`, `getCollectionPayableDetails`, `createOrUpdateCollectionLeadTask` (31 APIs) | 31 of 31 |
| **trustt-platform-api-gateway** | `getScheduleDetails`, `updateSchedulePayment`, `bulkUploadFile`, `updatePaymentStatus` | 4 of 4 |
| **novopay-platform-lib** / **trustt-platform-lib** | `bulkFileToSGNpHandoffJob`, `executeLCSPortfolioTransfer`, `rollbackLCSPortfolioTransfer` (same 3 in both — the lib fork pair) | 3 of 3 |
| **trustt-platform-accounting** | `cancelCollections`, `loanAccountCollection` | 1 of 2 (`cancelCollections` has the one undeclared-verify-mode case) |
| **trustt-platform-task** | `addContactForExternalCollectionCustomer`, `updateLocationForTaskIds` | 2 of 2 |
| **trustt-platform-los** | `updateCustomerPan` | 1 of 1 |

**Webapp**: 100 of the 275 apiNames appear as literal string matches under
`trustt-platform-webapp/**/*.ts(x)`/`*.js` (unfiltered — includes comments/log strings, not
narrowed to a `ui_reachable` field the way `.cursor/platform-api-map.md` does for accounting).
Treat as an upper bound, not a caller count; narrowing this list is worklist item below.

### 2.2 The three highest-blast-radius uncovered APIs

- **`cancelCollections`** (`trustt-platform-payments/deploy/application/orchestration/orc_mfi.xml:1326`)
  — called from **3 accounting money flows**: `individualChildLoanForeclosure`,
  `loanDisbursementCancellation`, `loanPrepayment`. Writes `collection`,
  `collection__sup_review_task_mapping`, `collection_history`, `priority_calendar_loan_details`;
  also calls out to `trustt-platform-task/updateTaskStatusForTaskIds`. This is the one apiName with
  a registry case (`foreclosure.cancel_collections`) — but the case only asserts JTF envelope
  `status`/`code`, not that `collection.status` actually transitioned or that the sup-review task
  was closed.
- **`updateCollectionCustomerInfo`** (`orc_mfi.xml:1805`) — called by
  `trustt-platform-actor/updateMFICustomerDetails` **and recursively by itself**
  (`trustt-platform-payments/updateCollectionCustomerInfo`, bulk path). Writes
  `collection_customer_info`. No case.
- **`fetchCollectionRecords`** (`orc_collections.xml:281`) — 9 processors, called by
  `trustt-platform-actor/allocateCollections` (the primary collector-allocation entry point) and
  `getCustomerDetailsForIVR`. Reads `collection`, `collection_attempts`, `collection_customer_info`.
  No case — a break here silently starves the collector allocation screen actor renders, the same
  failure shape as the `charges_configured` incident (accounting response contract breaking a
  different team's screen with no accounting-side signal).

---

## 3. Kafka surface

Payments touches **11** topics in `.cursor/event-registry.md`: 9 consumed, 2 produced (one of
which, `bulk_collection_data_failed_`, flows back to accounting; the other,
`collection_task_creation_`/`collection_task_processing_`, is produced *and* self-consumed).

| Topic | Direction | Consumer class | Idempotency posture | Runtime coverage |
|---|---|---|---|---|
| `bulk_collection_data_` | accounting → payments | `CreateOrUpdateBulkCollectionConsumer` | **DB-driven upsert** — `findCollectionByexternalId(extRefId)` then update-or-create (`CreateOrUpdateBulkCollectionConsumer.java:110-122`); no Redis lock, so two near-simultaneous deliveries of the same `col_ext_ref_id` can both read "not found" and double-insert | **zero** — no registry case |
| `bulk_collection_data_failed_` | payments → accounting | (accounting-side; `BulkCollectionFailedRecordConsumer`) | N/A (payments producer side) | zero |
| `collection_customer_details_` | actor → payments | `PopulateCollectionCustomerDetailsConsumer` | **not checked** — no `redis`/`hasKey`/dedup token found in the consumer class (`grep -in` empty) | zero |
| `collection_office_details_` | actor → payments | `CollectionOfficeDetailsConsumer` | same — no dedup found | zero |
| `collection_primary_allocation_` | payments (self) | `PrimaryAllocateCollectionConsumer` | same — no dedup found | zero |
| `collection_secondary_allocation_` | payments (self) | `SecondaryAllocateCollectionConsumer` | same — no dedup found | zero |
| `collection_task_creation_` | payments → task | (task-side `CollectionTaskCreationConsumer`) | N/A (payments producer side) | zero |
| `collection_task_processing_` | payments (self) | `CollectionTaskProcessingConsumer` | same — no dedup found | zero |
| `finnone_collection_task_creation_` | payments → task | (task-side) | N/A (payments producer side) | zero |
| `meeting_center_details_` | los/actor → payments | `PopulateMeetingCenterDetailsConsumer` | same — no dedup found | zero |
| `update_collection_task_details_` | task → payments | `UpdateCollectionTaskDetailsConsumer` | same — no dedup found | zero |

**Grep basis** (per consumer class, no hits in any of the 8 payments-side consumers):
```bash
grep -in "redis\|Redis\|CacheClient\|hasKey\|CannotAcquireLock\|dedup\|idempotent" \
  trustt-platform-payments/src/main/java/in/novopay/payments/collections/mfi/consumer/*.java
```
Zero matches across all 8 files (`CreateOrUpdateBulkCollectionConsumer`,
`PopulateCollectionCustomerDetailsConsumer`, `CollectionOfficeDetailsConsumer`,
`PrimaryAllocateCollectionConsumer`, `SecondaryAllocateCollectionConsumer`,
`CollectionTaskProcessingConsumer`, `PopulateMeetingCenterDetailsConsumer`,
`UpdateCollectionTaskDetailsConsumer`). Only `bulk_collection_data_` has any dedup shape at all,
and it is the find-or-create pattern above — not a lock. `.cursor/event-registry.md:76` already
records this one as "Partial — DB-driven"; the other seven have no equivalent line in the registry
today (their entries say "Error handling: Y" but do not comment on idempotency), which this report
adds.

**A concrete non-idempotency finding** (read, not fixed — read-only task):
`CreateOrUpdateBulkCollectionConsumer.parseData` (`CreateOrUpdateBulkCollectionConsumer.java:127-136`)
catches `JSONParser` failure, logs, and returns `null` with the comments `// What to throw here` /
`// Do we need to push here` left in place — a malformed message is silently swallowed with **zero**
downstream signal, consistent with the `events.md` warning about consumer catch paths that swallow
and commit silently. Not in `.cursor/gaps-and-risks.md` today under any GAP-id found by a scan of
`payments|collection` rows — worth a digest entry if the user wants one opened (not done here per
the read-only scope of this task).

**Zero runtime coverage across all 11 topics** — no registry case with `type: kafka` or a topic
name matching any of the 11 was found in `scripts/testing/registry.json`.

---

## 4. Top 10 worklist — money first

Every table/column named against `platform_lookup.py`/`platform_api_map.py` output, not memory.

| # | Flow | Why money-first | Assert a real case would need | Fails on |
|---|---|---|---|---|
| 1 | `cancelCollections` `orc_mfi.xml:1326` | 3 accounting money flows depend on it (`individualChildLoanForeclosure`, `loanDisbursementCancellation`, `loanPrepayment`); the one existing case only checks the envelope | `collection.status` transitions to closed/cancelled for the account; `collection__sup_review_task_mapping` row closed; `updateTaskStatusForTaskIds` call to task fired | foreclosure/disbursement-cancellation leaving a stale open collection row that the collector queue still surfaces |
| 2 | `updateCollection` `orc_collections.xml:87` | 3 processors, 10+ tables written (`collection`, `collection_attempt_history`, `collection_employee_info(_history)`, `collection_office_info`, `collection_reference_details(_history)`, `priority_calendar_loan_details`, …); self-called from `fetchLMSUpdate` batch | Per-table row presence is not enough — assert the specific `collection.status`/employee-assignment fields that `fetchLMSUpdate` (item 6 below) depends on | LMS sync silently updating the wrong collection row |
| 3 | `fetchCollectionRecords` `orc_collections.xml:281` | Feeds `actor/allocateCollections` — the primary collector-assignment screen | `collection`/`collection_attempts`/`collection_customer_info` rows returned match the `dpd_bucket_id`/`office_id`/`collector_id` filters in the request | a collector's queue silently missing or double-counting accounts |
| 4 | `bulk_collection_data_` consumer (`CreateOrUpdateBulkCollectionConsumer`) | Entry point for every LMS-generated due into payments; find-or-create with no lock | replay the same `col_ext_ref_id` twice in one poll window and assert exactly one `collection` row, not two | the described double-insert race on concurrent delivery |
| 5 | `updateCollectionCustomerInfo` `orc_mfi.xml:1805` | Called by actor's `updateMFICustomerDetails` **and** recursively by itself (bulk path) — a self-referencing contract with no guard visible in this map | `collection_customer_info` reflects the request payload after both the single and bulk path, and the bulk path does not re-trigger a further self-call loop | demographic edits from actor landing on the wrong collection or looping |
| 6 | `markCollectionsAsSettled` / `reconcileCollectionPayments` (`orc_collections.xml:574`, `:564`) — both called only from `collectionPaymentSettlementBatch` | Settlement/reconciliation is money-state-changing and currently has **zero** callers outside the batch that owns it, i.e. it is untested end to end including the batch trigger | `collection_activity`, `collection_payment_tracking_details(_history)` reflect the settled amount; batch actually reaches `COMPLETED` | settlement batch reporting success while `collection_payment_tracking_details` still shows the pre-settlement state (same failure shape accounting's `batch.loan_advance_repayment` case already documents for its own domain) |
| 7 | `loanAccountCollection` (accounting-side apiName, called from `trustt-platform-accounting/loanPrepayment`) — the **payments→accounting direction is out of this repo's scope but the caller-side contract is not**, cross-reference `.cursor/accounting-coverage-map.md` §3 item mapping | Prepayment depends on this; already flagged accounting-side as UNCOVERED | (owned by the accounting coverage map, not duplicated here) | — |
| 8 | `getUpdatedAmountOfCollection` `orc_collections.xml:407` | Called by 2 actor task-detail screens (`collectionDetailsForTask`, `getCollectionDetails`) | the amount returned matches the live `collection`/due-detail state, not a stale snapshot | agent sees an outdated collectable amount |
| 9 | `getCollectionMISReportDetails` / `getCollectionAttemptsReportDetails` / `getSettlementMISReportDetails` — 3 batch-report apiNames each with exactly 1 actor caller (`generateCollectionMISReportInBatch`, `generatecollectionAttemptMTDReportBatch`) | Reporting integrity for MIS — wrong numbers here are a business-visibility defect, lower money-risk than 1-6 but currently fully dark | row counts / one sampled row's key fields match a seeded fixture | a report silently under/over-counting collections |
| 10 | Kafka: `collection_customer_details_`, `collection_office_details_`, `meeting_center_details_`, `update_collection_task_details_` consumers | 4 of the 11 topics with **zero** idempotency guard *and* zero runtime coverage — cheapest fix-class (add a case that replays the same message twice and asserts row count, not value) before attempting the harder money asserts above | row count stays 1 after 2x replay | duplicate rows accumulating silently on redelivery |

---

## Single highest-value next action

**Build `scripts/lib/payments_flow_domains.json`** (the payments equivalent of
`scripts/lib/accounting_flow_domains.json`) and wire it into a
`scripts/bin/payments-flow-coverage.sh`, seeded from the 275-apiName inventory in §1 with domains
at minimum: `collections_intake` (bulk/Kafka consumers), `allocation` (primary/secondary
allocation + `fetchCollectionRecords`), `settlement_reconciliation` (`markCollectionsAsSettled`,
`reconcileCollectionPayments`), `customer_office_sync`, `foreclosure_cancellation_hooks`
(`cancelCollections`, `loanAccountCollection`), `reporting_batch`, `bulk_file_sg_*` (66
batch/job apiNames). Without this, every future payments coverage conversation restarts from
"1 of 275" instead of a domain-scoped gap count the way accounting's
`accounting-flow-coverage.sh` already gives that module — and it is the same shape of file, so it
is a low-effort, high-leverage mirror of work already proven to pay off once.

Second-priority, cheaper action: add the value-level assert to the one existing case
(`foreclosure.cancel_collections`) — it already runs, it just checks the wrong thing (envelope,
not `collection.status`) — before writing any new cases.
