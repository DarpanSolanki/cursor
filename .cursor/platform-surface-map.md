# Platform surface map (generated — do not hand-edit)

`python3 scripts/testing/platform_surface.py` regenerates this from the KG.
Companion to `.cursor/platform-api-map.md`, which maps what a caller can invoke;
this maps the four surfaces incidents actually arrive through.

| Surface | Mapped | Detail |
|---------|-------:|--------|
| Kafka topics | 153 | `cursor-bundle/flow-test/platform_events.jsonl` |
| Schedulers | 368 | `cursor-bundle/flow-test/platform_schedulers.jsonl` |
| Tables | 871 | `cursor-bundle/flow-test/platform_tables.jsonl` |
| Error codes | 1852 | `cursor-bundle/flow-test/platform_errors.jsonl` |

## Events

- **153 topics**, 151 with a known consumer.
- **2 with no consumer indexed** — either produced for an external
  system, or a message going nowhere. `events.md` requires a consumer and a failure
  posture in the same change set, so these are worth a look, not an alarm:

  - `key` — produced at `trustt-platform-actor/src/main/java/in/novopay/actor/bulk/ucic/writer/SGToUCICUpdateIWriter.java`
  - `update_customer_loan_details_failed` — produced at `trustt-platform-actor/src/main/java/in/novopay/actor/customer/util/UpdateCustomerLoanDetailsConsumer.java`

**Indexing artefact, not a topic:** 1 entr(y/ies) came from a variable rather than a literal — `key`. The producer passes the topic name in, so the KG recorded the parameter.
Unknown, not orphan.

## Schedules

- **368 schedulers** across 12 repos: reporting 106, accounting 102, payments 58, los 51, actor 28, task 10, batch 4,  4
- **17 trigger no request the KG can name.** 14 of those
  come from `.cursor/scheduler-registry.md` rather than code — documented names,
  not indexed beans. The other 3:

  - `collToStagNpReverseHandOffSyncJob` — `trustt-platform-payments/src/main/java/in/novopay/payments/batch/finnone/config/CollToStagNpReverseHandOffSyncBatchConfigService.java`
  - `job_name` — `trustt-platform-reporting/src/main/java/in/novopay/batch/uam/status_enquiry/GetStatusEnquiryForScheduledReportsProcessor.java`
  - `reTriggerServiceStatus` — `trustt-platform-los/src/main/java/in/novopay/los/batch/servicestatus/ReTriggerServiceStatusConfigService.java`

## Data

- **871 tables**, 435 with an API that writes them.
- **830 carry their live column shape**
  — columns, primary key, FK and index counts — joined from the schema oracle
  (`cursor-bundle/schema/tables.jsonl`) rather than re-derived. Resolve a column
  here before naming it: `40-knowledge-upkeep.md` treats a column written from
  memory as a guess.
- **41 are known to the KG but absent from the local DB.** That is train divergence, not proof the table does
  not exist — say which branch you read.
- **436 have no writer reachable from any API** — written by a batch
  writer, a migration, or nothing at all.
- **1 is not a table name at all** ('\\') — a DAO call the KG could not resolve. Flagged rather than dropped or counted as a table.
- Most-written tables (writer count is a blast-radius proxy):

  - `loan_app` — 81 APIs, 70 columns
  - `group_details` — 53 APIs, 80 columns
  - `loan_account` — 37 APIs, 84 columns
  - `collection` — 35 APIs, 93 columns
  - `group__task_details` — 31 APIs, 13 columns
  - `borrower` — 30 APIs, 59 columns
  - `employee` — 30 APIs, 35 columns
  - `loan_app__document_details` — 29 APIs, 22 columns
  - `loan_app__task_details` — 29 APIs, 13 columns
  - `user_activity_location` — 29 APIs, 8 columns
  - `address` — 24 APIs, 17 columns
  - `dot_account_creation_details` — 23 APIs, 21 columns

## Errors

- **1852 codes** indexed with their throw site and branches.
- **1426 are reachable from a mapped API**; the remaining
  426 are thrown from batch writers, consumers and platform-lib —
  reachable in production, just not via an orchestration entry point.
- `kg_error <code>` returns the throw sites, the ExecutionContext keys the message
  template needs, and prior fixes for ~160 tokens. Use it before grepping.

## GL posting rules

- **187 posting rules** across **17 transaction types** (4 further `gl_rule` nodes are cross-check entries, not rules).
  Each names its
  leg sequence, `reference_code`, and the debit/credit placeholders that resolve
  to internal accounts through `product_transaction_catalogue__placeholder__iad`.
- **Every rule names both a debit and a credit placeholder.** A rule with one side is the first thing to check when a posting lands nowhere; there are none.
- `selected_by` names the processor whose `sets_txn_type` chooses the type, so a
  GL question resolves in one hop instead of two searches.

| Transaction type | rules |
|---|---:|
| `LOAN_PREPAYMENT` | 25 |
| `DEATH_FORECLOSURE` | 22 |
| `RSCH_DEATH_FORECLOSURE` | 22 |
| `LOAN_DISB_CNCL` | 19 |
| `RSCH_LOAN_DISB_CNCL` | 19 |
| `RSCH_LOAN_PREPAYMENT` | 16 |
| `LOAN_PART-PREPAYMENT` | 14 |
| `LOAN_DISBURSEMENT` | 11 |
| `LOAN_REPAYMENT` | 11 |
| `INTEREST` | 6 |
| `EXCESS_AMT_REFUND` | 4 |
| `LOAN_REBOOKING` | 4 |

## Processors

- **3745 processors**, 72 of them running in flows across more
  than one repo. Editing a shared processor is a cross-service change whether or
  not the diff says so.
- **1112 write to a table** — the set where `no-flow-break-impact-check`
  and the money gates apply.
- Most-reused, by number of distinct flows that invoke them:

| Processor | flows | repos | writes |
|---|---:|---:|---:|
| `dummyProcessor` | 323 | 9 | 0 |
| `populateUserDetails` | 122 | 5 | 0 |
| `populateUserStoryProcessor` | 120 | 4 | 0 |
| `constructRequestDataForApproval` | 104 | 5 | 0 |
| `fetchBulkUniqueMasterData` | 101 | 3 | 0 |
| `setCommonAttributesProcessor` | 98 | 5 | 0 |
| `getMakerCheckerEnabledForUseCaseProcessor` | 87 | 5 | 0 |
| `deleteDraftProcessor` | 78 | 6 | 0 |
| `constructRequestForApprovalUsingApprovalTemplate` | 48 | 2 | 0 |
| `populateCurrentDateProcessor` | 41 | 3 | 0 |
| `setUserStoryForResponseProcessor` | 41 | 3 | 0 |
| `deleteCachedKeysProcessor` | 39 | 4 | 0 |

`dummyProcessor` tops that list at 327 flows and is exactly what it sounds like —
reuse count alone is not risk. Read the `writes` column beside it.

