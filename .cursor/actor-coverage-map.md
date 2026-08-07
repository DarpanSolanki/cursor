# Actor coverage — apiName inventory + reverse contract boundary

Scope: `trustt-platform-actor`. Measured 2026-08-08 against `mfi_integration_v3.7.1`
(`770b97aef4`). Methodology mirrors `.cursor/accounting-coverage-map.md` and
`scripts/scratch/internal-caller-map/REPORT.md` (the accounting internal-caller report) —
read those first if this format is unfamiliar.

**Everything here runs correctly in production.** An uncovered apiName is a gap in *this test
suite*, not a product defect.

## Provenance

```
python3 -c "..." # parsed cursor-bundle/flow-test/platform_api_map.jsonl (skip line 1, a comment) for repo == trustt-platform-actor
rg --no-ignore -n 'callInternalAPI\(' -g '*.java' -g '!**/build/**' -g '!**/test/**' .
```

**Gotcha worth recording**: `rg`/`grep -r` run from the workspace root silently return **zero**
matches for `*.java` files, with no error, because the root `.gitignore` is `*` with narrow
allowlists (`.cursor/`, docs, etc.) and ripgrep honours `.gitignore` by default even outside a
git operation. Every service-repo file is invisible to a plain `rg -g '*.java' .` from root.
Fix: `--no-ignore`, or scope the search inside the repo directory. This cost real time on this
task and is worth remembering for the next repo-wide grep from workspace root.

Raw intermediates: `scripts/scratch/actor-coverage-map/actor_apis.json` (473 actor apiName
records from the generated map), `actor_callers_found.json` (340 `callInternalAPI` literal
matches whose string argument is an actor apiName, 316 external to `trustt-platform-actor`),
`registry_coverage.json` (registry cases indexed by `api`/`apis`), `summary.json`.

---

## 1. Actor apiName inventory

**473 live orchestration apiNames** are attributed to `trustt-platform-actor` in the generated
map (`cursor-bundle/flow-test/platform_api_map.jsonl`, `repo == "trustt-platform-actor"`).
Unlike accounting, actor serves **multiple tenant product lines** through the same service —
the orchestration file each apiName lives in tells you which:

| Orchestration file | apiNames | Product line |
|---|---:|---|
| `orc_mfi.xml` | 149 | MFI (this workspace's primary domain) |
| `orc_mfi2.xml` | 90 | MFI |
| `ServiceOrchestrationXML.xml` | 77 | Common/shared (login, office, employee — used across tenants incl. MFI) |
| `orc_collections.xml` | 59 | MFI collections |
| `waas_ekyc_orc.xml` | 24 | WAAS eKYC (non-MFI) |
| *(no orchestration path in map)* | 20 | Unresolved |
| `bp_card_orc_xml.xml` | 7 | BP (non-MFI) |
| `insurance_orc.xml` | 5 | Insurance (cross-tenant) |
| `waas_card_orc.xml` | 4 | WAAS (non-MFI) |
| `product_corporate_employee_orc.xml` | 4 | Product/corporate (non-MFI) |
| `bp_customer_orc_xml.xml` | 4 | BP (non-MFI) |
| `waas_customer_faq.xml` | 4 | WAAS (non-MFI) |
| remaining 12 files | ≤3 each, 26 total | BP/IDFCP/WAAS/product (non-MFI) |

**298 of 473 (63%)** sit in the two MFI files plus collections (`orc_mfi.xml` + `orc_mfi2.xml`
+ `orc_collections.xml`); the rest are other-tenant surface that this workspace does not
otherwise track. The worklist below (Sections 2–3) is not filtered by product line — a
cross-service Java call site is evidence regardless of which orchestration file declares the
apiName, and in practice every cross-service caller found lands in an MFI-domain apiName.

### Coverage against `scripts/testing/registry.json`

Joined on each case's **`api`** field and its **`apis`** list — never the case id (same rule
`.cursor/accounting-coverage-map.md` states, for the same reason: a case-id match once produced
a duplicate).

| | |
|---|---:|
| Actor apiNames total | **473** |
| Matched by ≥1 registry case (`api`/`apis`) | **2** |
| `verify_mode` declared on either | **0** (both `None`) |
| Coverage % (strict grading, `verify_mode` required) | **0%** |
| Actor-specific registry cases found | `actor.user_basic` → `getUserBasicDetails`, `actor.office_by_ids` → `getOfficeCodeAndNameByIds` |
| Plus | `health.actor` — service health probe, not an apiName case |

Both cases are **not theatre** — they make the real HTTP round trip and assert response values
(`actor.office_by_ids` has `expect.path_eq: {"office_list[0].office_details.id":
"${OFFICE_ID}"}`; `actor.user_basic` has `path_eq` on `user_basic_details.id` and
`user_basic_details.status`). The gap is narrow but real: neither declares `verify_mode`, so per
the grading table below (mirrored from the accounting report) the ship gates cannot tier them,
and by the accounting report's own convention ("case, no `verify_mode`" = uncovered) they count
as uncovered here too.

| `verify_mode` | Verdict | Count |
|---|---|---:|
| `runtime` / `RUNTIME_VERIFIED` | covered | 0 |
| `WORKSPACE_ONLY` | UNCOVERED — theatre | 0 |
| `processor_mirror_sim` / `orch_sibling_sim` | not covered | 0 |
| absent / `None` (case exists, asserts values, no tier declared) | not covered (undeclared) | **2** |
| no case at all | not covered | **471** |

**Everything else — 471 of 473 actor apiNames — has zero registry footprint of any kind.** This
is a starker number than accounting's 8.5%, and the reason is structural, not that actor is
riskier: accounting has 90 registry cases total workspace-wide and most target accounting money
paths (disbursement, repayment, DPI, foreclosure); actor has never been a first-class test
target in this suite — its only two cases exist because something else's flow needed office/user
lookup data along the way.

---

## 2. Actor as a contract boundary (reverse direction)

**Known direction (already documented):** actor calls accounting's `getLoanProductList` from
~8–12 validators to read `product_code_list` (`.cursor/rules/api-catalogue` /
`scripts/scratch/internal-caller-map/REPORT.md` row 1).

**This section is the reverse:** which actor APIs does accounting/LOS/payments/task/reporting
call, found by literal-scanning every repo's Java for
`callInternalAPI(ctx, "<apiName>", ...)` where `<apiName>` is one of the 473 actor apiNames from
Section 1. No direct `WebClient`/`RestTemplate` calls into actor endpoints were found outside
this pattern (`rg --no-ignore -in "webclient|resttemplate" ` scoped to actor-mentioning files
returned nothing beyond the internal-API-client wrapper) — `callInternalAPI` is the sole
cross-service mechanism into actor, same as accounting.

### 2a. The methodology finding, reproduced for actor

Same defect as the accounting report: `called_by` in the generated map is derived from
orchestration `<Request name=...>` nodes, so it only sees a caller when the *calling*
orchestration flow declares a `<Request>` sub-call to the target apiName. A **Java** call via
`NovopayInternalAPIClient.callInternalAPI(...)` inside a plain service/util class (no
orchestration `<Request>` node wrapping it) is invisible to the generator.

**72 of the 98 actor apiNames with a Java-literal external caller have at least one caller-repo
missing from their `called_by` list.** Examples (full list:
`scripts/scratch/actor-coverage-map/summary.json` → `missed`):

| apiName | Java-grep found caller repos | `called_by` in generated map | Repos the map misses |
|---|---|---|---|
| `getOfficeDetails` | los, payments, accounting, actor, task | accounting, actor, task | **los, payments** |
| `getCustomerDetails` | accounting, los, payments | accounting, los | **payments** |
| `getUserDetails` | accounting, approval, authorization, masterdata-management, task, batch, los, payments, reporting | accounting, approval, authorization, masterdata-management, task | **batch, los, payments, reporting** |
| `getBankEmployeeDetails` | accounting, actor, masterdata-management, task, los, payments, reporting | accounting, actor, masterdata-management, task | **los, payments, reporting** |
| `getEmployeeNameList` | los, reporting, task | *(empty)* | **los, reporting, task** (100% missed) |
| `getUserIdListByEmployeeIds` | payments, task | *(empty)* | **payments, task** (100% missed) |
| `getVtcDetailsById` | los, payments, task | *(empty)* | **los, payments, task** (100% missed) |
| `getVillageRiskMappingForVtcList` | los, reporting | *(empty)* | **los, reporting** (100% missed) |
| `getAddressFromVtc` | los | *(empty)* | **los** (100% missed) |
| `validateFinnoneInboundData` | payments | *(empty)* | **payments** (100% missed) |

Anyone doing the `api-contract-safety.md` "find all callers" step from `called_by` alone for,
say, `getEmployeeNameList` would conclude actor has zero callers to check before changing its
response shape. It has three services' worth.

### 2b. The caller-ranked table (top 15 by distinct external Java call sites)

`callers` = distinct `file:line` sites outside `trustt-platform-actor` matching
`callInternalAPI(ctx, "<apiName>", ...)`. Coverage verdict per Section 1 (registry `api`/`apis`
match; `verify_mode` required to count as covered).

| # | apiName | callers | who calls it | coverage verdict |
|---|---|---:|---|---|
| 1 | `getOfficeDetails` | **29** | payments (`PriorityCalendarService`), task (`ActorAPIUtil`, `TaskDao`), accounting, actor | UNCOVERED (no case) |
| 2 | `getCustomerDetails` | **28** | payments (`PriorityCalendarService`, `MfiUtility`, `PriorityCalendarUtil`), los (`GetDDEBorrowerDetailsProcessor`), accounting | UNCOVERED (no case) |
| 3 | `getUserDetails` | **22** | task (`RejectTaskPushNotificationProcessor`, `TaskEmailNotificationProducer`, `TaskSMSNotificationProducer`), accounting, approval, authorization, masterdata-management, batch, los, payments, reporting | UNCOVERED (no case) |
| 4 | `getEmployeeDetails` | **18** | task (`ActorAPIUtil`, `TaskDao`), payments (`ViewUniqueCollectorProcessor`, `GetCollectionProcessor`), accounting, actor, los | UNCOVERED (no case) |
| 5 | `getBankEmployeeDetails` | **14** | task (`RejectTaskPushNotificationProcessor`, `TaskEmailNotificationProducer`, `TaskSMSNotificationProducer`), los, payments, reporting | UNCOVERED (no case) |
| 6 | `getOfficeList` | **12** | task (`ActorAPIUtil`, `GetAllChildrenOfOfficeProcessor`, `GetImmediateChildrenOfOfficeProcessor`), payments (`GetCollectionSummaryProcessor`), accounting, los, reporting | UNCOVERED (no case) |
| 7 | `getOfficeCodeAndNameByIds` | **11** | task (`GetTaskListForDeligationProcessor`, `TaskCommonUtil`, `PopulateTaskOfficeProductProcessor`), los (`ActorUtil.java:1065`), accounting, reporting | **case exists, no `verify_mode`** — `actor.office_by_ids` |
| 8 | `getEmployeesIdListUnderUserId` | **10** | payments (`GetSupervisorReviewsUnderUserProcessor`, `SubmitSupervisoryReviewProcessor`, `MfiUtility`, `ActorApiUtility`), los, reporting, approval | UNCOVERED (no case) |
| 9 | `getCustomerDetailsForCollection` | **7** | payments (`GetTransactionsForCollectorProcessor`, `GetAllocationStatusDetailsProcessor`, `GetCollectionStatusDetailsProcessor`, `GetDpdBucketDetailsProcessor`), los | UNCOVERED (no case) |
| 10 | `getUserBasicDetails` | **5** | task (`ActorAPIUtil`), payments (`MfiUtility`, `ActorApiUtility`), los (`ActorUtil.java:612`) | **case exists, no `verify_mode`** — `actor.user_basic` |
| 11 | `getOfficeNameByEmployeeId` | 5 | reporting, los | UNCOVERED (no case) |
| 12 | `getUniqueInsuranceProviderCodeAndName` | 5 | (payments/los — insurance display) | UNCOVERED (no case) |
| 13 | `getTaskDataFromCollection` | 4 | payments, reporting, task, accounting | UNCOVERED (no case) |
| 14 | `getEmployeeServiceableOffices` | 4 | payments, accounting | UNCOVERED (no case) |
| 15 | `getEmployeeNameList` | 4 | los, reporting, task | UNCOVERED (no case) — **100% missed by generated map** |

Full 98-apiName table: `scripts/scratch/actor-coverage-map/summary.json` (`api_counts`).

### Counts

| | |
|---|---:|
| Actor apiNames total | 473 |
| With ≥1 external Java `callInternalAPI` call site | **98** |
| Total external call sites found | **316** |
| Of those 98, matched by a registry case with a `verify_mode` | **0** |
| Of those 98, matched by a registry case with **no** `verify_mode` | **2** (`getOfficeCodeAndNameByIds`, `getUserBasicDetails`) |
| Of those 98, **fully uncovered** | **96 (98%)** |

By consuming service (distinct actor apiNames each service calls, from the 98):

| Consuming service | distinct actor apiNames called |
|---|---:|
| **trustt-platform-los** | 57 |
| **trustt-platform-payments** | 32 |
| **trustt-platform-accounting** | 24 |
| **trustt-platform-reporting** | 20 |
| **trustt-platform-task** | 18 |
| trustt-platform-approval | 2 |
| trustt-platform-bre | 1 |
| trustt-platform-masterdata-management | 1 |
| trustt-platform-batch | 1 |
| trustt-platform-notifications | 1 |

LOS and payments are actor's two heaviest downstream dependents by distinct-API count — the
same two services the accounting report found leaning hardest on accounting's read surface, for
the same reason: both are front-line orchestration services that resolve office/customer/user
context per request rather than caching it.

---

## 3. Top 10 worklist — uncovered + cross-service-called, ranked by caller count

All 10 qualify (uncovered × caller_count > 0); no padding needed. Evidence is `file:line` from
the literal scan (`scripts/scratch/actor-coverage-map/actor_callers_found.json`), one sample
site per calling repo shown, full list in that file.

| # | apiName | callers | Evidence (`file:line`) | Break looks like |
|---|---|---:|---|---|
| 1 | `getOfficeDetails` | 29 | `trustt-platform-payments/src/main/java/in/novopay/payments/batch/service/PriorityCalendarService.java:281`, `:550`; `trustt-platform-task/src/main/java/in/novopay/task/util/ActorAPIUtil.java:104` (`apiClient.callInternalAPI(newContext, "getOfficeDetails", "v1", "getOfficeDetails_response", 5000, 5000, false)`, wrapped to `LOS-0192` on failure) | Office resolution silently returns wrong/blank office name or code into three services' calendars, task routing, and accounting internal-account setup with no test catching a shape change |
| 2 | `getCustomerDetails` | 28 | `trustt-platform-payments/.../batch/service/PriorityCalendarService.java:623`; `.../collections/mfi/util/MfiUtility.java:448`; `.../collections/mfi/util/PriorityCalendarUtil.java:177`; `trustt-platform-los/src/main/java/in/novopay/los/processor/GetDDEBorrowerDetailsProcessor.java:102` | Widest accounting dependency too (`called_by` already lists 20 accounting apiNames incl. `disburseLoan`, `loanDeathForeclosure`) — a field drift here fans out across disbursement, DDE borrower lookup, and payments priority calendars simultaneously |
| 3 | `getUserDetails` | 22 | `trustt-platform-task/src/main/java/in/novopay/common/RejectTaskPushNotificationProcessor.java:117`, `:188`; `TaskEmailNotificationProducer.java:159`; `TaskSMSNotificationProducer.java:159` | Task notification pipeline (email/SMS/push reject-notice) silently drops recipient details; widest caller-repo count of any actor API (9 repos) |
| 4 | `getEmployeeDetails` | 18 | `trustt-platform-task/src/main/java/in/novopay/task/util/ActorAPIUtil.java:243`; `trustt-platform-payments/.../collections/processor/ViewUniqueCollectorProcessor.java:150`; `GetCollectionProcessor.java:57` | Collections views resolve the wrong collector identity to a borrower-facing screen |
| 5 | `getBankEmployeeDetails` | 14 | `trustt-platform-task/src/main/java/in/novopay/common/RejectTaskPushNotificationProcessor.java:130`, `:211`; `TaskEmailNotificationProducer.java:175` | Same notification fan-out as `getUserDetails` but for bank-employee identity — reject-task emails/SMS go to the wrong or blank recipient |
| 6 | `getOfficeList` | 12 | `trustt-platform-task/src/main/java/in/novopay/task/util/ActorAPIUtil.java:324`; `GetAllChildrenOfOfficeProcessor.java:95`; `trustt-platform-payments/.../collections/processor/GetCollectionSummaryProcessor.java:76` | Office hierarchy pagination drift truncates collection summaries and task office trees across two services silently |
| 7 | `getOfficeCodeAndNameByIds` | 11 | `trustt-platform-task/.../GetTaskListForDeligationProcessor.java:140`; `TaskCommonUtil.java:528`; `trustt-platform-los/src/main/java/in/novopay/los/util/ActorUtil.java:1065` | Case exists (`actor.office_by_ids`) and asserts values — **only missing `verify_mode`**; cheapest of the 10 to close (declare the tier, do not build a new case) |
| 8 | `getEmployeesIdListUnderUserId` | 10 | `trustt-platform-payments/.../collections/mfi/processor/GetSupervisorReviewsUnderUserProcessor.java:44`; `SubmitSupervisoryReviewProcessor.java:96`; `.../mfi/util/MfiUtility.java:348` | Supervisory-review chain resolves the wrong subordinate-employee set — a review gets routed or approved against the wrong reporting line |
| 9 | `getCustomerDetailsForCollection` | 7 | `trustt-platform-payments/.../collections/processor/GetTransactionsForCollectorProcessor.java:63`; `GetAllocationStatusDetailsProcessor.java:158`; `GetCollectionStatusDetailsProcessor.java:76` | Collector-facing collection status/allocation screens show wrong customer identity — field-agent-visible, no test |
| 10 | `getUserBasicDetails` | 5 | `trustt-platform-task/src/main/java/in/novopay/task/util/ActorAPIUtil.java:206`; `trustt-platform-payments/.../collections/mfi/util/MfiUtility.java:637`; `trustt-platform-los/src/main/java/in/novopay/los/util/ActorUtil.java:612` | Same nuance as #7 — case exists (`actor.user_basic`), asserts `user_basic_details.id`/`.status`, only missing `verify_mode` |

---

## Highest-value next action

**Declare `verify_mode: runtime` (or the correct tier) on the two existing cases —
`actor.office_by_ids` and `actor.user_basic` — first.** They already make the real call and
assert response values (`path_eq` on the returned id, status), so this is a one-line registry
edit, not new test code, and it immediately moves 2 of the top-10 cross-service-called APIs from
undeclared to covered.

**Then add one contract-smoke case for `getOfficeDetails`.** It is the single densest uncovered
node: 29 call sites across payments, task, accounting, and actor itself — the highest caller
count of any actor apiName in this scan, uncovered by any case, and (per Section 2a) the
generated `called_by` map already misses two of its five caller repos (los, payments), so a
contract change here is exactly the shape of break the `charges_configured` precedent
(`.cursor/rules/api-contract-safety.mdc`) warns about: it would not show up as an accounting-side
or actor-side test failure, only as a silent wrong-value read three services away.

## Caveats

- Actor serves several non-MFI product lines (BP, IDFCP, WAAS, generic product/corporate) through
  the same orchestration engine; Section 1's 473-apiName denominator includes all of them because
  the generated map does not tag product line, but every cross-service caller found in Section 2
  targets an MFI-domain apiName (`orc_mfi.xml` / `orc_mfi2.xml` / `orc_collections.xml` /
  `ServiceOrchestrationXML.xml` common surface).
- No direct `WebClient`/`RestTemplate` call into actor was found outside the
  `NovopayInternalAPIClient.callInternalAPI` wrapper — the literal scan is the complete picture of
  the Java cross-service surface, same conclusion as the accounting report.
- **Everything here runs correctly in production.** Every gap named is a test-suite gap, not a
  product defect.
- This is read-only research: no registry edits, no KG rebuild, no service source touched.

## Pairs with

`.cursor/accounting-coverage-map.md` (methodology precedent) ·
`scripts/scratch/internal-caller-map/REPORT.md` (the `called_by`-undercounts-Java-callers finding,
first documented for accounting, reproduced here for actor) ·
`.cursor/rules/api-contract-safety.mdc` (the `charges_configured` incident this pattern predicts) ·
`.cursor/platform-api-map.md` (generated map this doc supplements, does not replace)
