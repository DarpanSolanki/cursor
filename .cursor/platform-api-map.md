# Platform API map (generated — do not hand-edit)

`python3 scripts/testing/platform_api_map.py` regenerates this from every service
repo's orchestration, its shipped JTF templates and the KG. These APIs run in
production; this records what they are, not what they should be.

**Control fields are headers**, never body: `function_code`, `function_sub_code`,
`run_mode`. Sent in the body the gateway answers `11008 Invalid run_mode`.

Per-API detail — request/response field paths, processor order, control branches —
is in `cursor-bundle/flow-test/platform_api_map.jsonl`, one JSON object per API.

## Reach

```
repo                                      apis orchestration   request  response     procs    tables    errors     calls    routed        ui   callers
------------------------------------------------------------------------------------------------------------------------------------------------------
trustt-platform-accounting                 360       351       346       345       351       262       280       125       338       158        68
trustt-platform-actor                      473       453       464       464       452       357       369        94       459       160       109
trustt-platform-api-gateway                 15        11         6         6        11         6         8         0        10         2         4
trustt-platform-approval                    15        14        15        15        14        12        14         6        15         9         5
trustt-platform-audit                        7         7         6         7         7         1         6         2         6         1         2
trustt-platform-authorization               27        25        27        27        25        23        22         5        27         7        20
trustt-platform-batch                       25        22        25        25        22        20        18         2        17        10         1
trustt-platform-dms                          8         6         8         8         6         6         6         1         6         2         4
trustt-platform-los                        517       489       503       497       488       406       405        67       486       175        41
trustt-platform-masterdata-management       38        36        38        38        36        28        29         3        37        15        15
trustt-platform-notifications               21        17        20        20        17        15        10         3        20         3         7
trustt-platform-payments                   275       254       265       266       254       181       234        31       258        59        26
trustt-platform-reporting                  119       119       117       115       119        70        18         2       114         7         3
trustt-platform-task                        52        49        52        52        49        22        40        15        50        14        13
------------------------------------------------------------------------------------------------------------------------------------------------------
TOTAL                                     1952      1853      1892      1885      1851      1409      1459       356      1843       622       318
```

`callers` answers the first line of the contract-safety checklist — *find all
callers* — without a fifteen-repo grep. The most-depended-on APIs, by number of
distinct calling flows:

| API | served by | called by |
|-----|-----------|----------:|
| `submitApplication` | approval | 49 |
| `getUserDetails` | actor | 45 |
| `getRoleDetailsByUserId` | authorization | 45 |
| `getEmployeeDetails` | actor | 42 |
| `getNotificationMessageByNotificationCode` | notifications | 42 |
| `getCustomerDetails` | actor | 33 |
| `getOfficeDetails` | actor | 32 |
| `getOfficeDetails` | api-gateway | 32 |
| `postTransaction` | accounting | 29 |
| `getDatatypeMaster` | masterdata-management | 26 |
| `getUserBasicDetails` | actor | 24 |
| `getLoanProductList` | accounting | 18 |
| `getUseCaseDetails` | authorization | 17 |
| `uploadDocument` | dms | 17 |
| `getRoleDetails` | authorization | 15 |

Changing one of these is a platform event, not a service change. The callers are
listed per API in the jsonl, repo-qualified.

`routed` = the API is in `platform_master.api_master`, the registry the gateway
routes on. The two disagree in both directions and the disagreement is recorded in
`cursor-bundle/flow-test/api_registry_reconciliation.json`:

- **registered, not served here** — mostly other product lines (AEPS, BillPay,
  bank-in-a-box). They exist only in the `api_master` seed migration, in no repo's
  orchestration. Absence here is not a defect; it means the code lives elsewhere.
- **served, not registered** — reachable in orchestration but not routed by the
  gateway. Internal-only flows and batch entry points, called service-to-service.

## trustt-platform-accounting

- **APIs:** 360 (89 mutating, 271 read/inquiry)
- **Tables written:** 133 — `account`, `account_balance`, `account_entry`, `account_interest_details`, `asset_classification_master`, `asset_classification_slabs`, `asset_criteria_group`, `asset_criteria_master`, `asset_criteria_slabs`, `base_interest_date_slab`, `base_interest_master`, `base_interest_slab`, `child_general_ledger`, `client_reference_number` (+119 more)
- **APIs calling another service:** 105
- **Depends on:** `trustt-platform-actor`, `trustt-platform-approval`, `trustt-platform-authorization`, `trustt-platform-los`, `trustt-platform-masterdata-management`, `trustt-platform-notifications`, `trustt-platform-payments`, `trustt-platform-task`
- **Largest flows:** `loanPrepayment` (110), `loanDeathForeclosure` (107), `createOrUpdateProductScheme` (88), `loanDisbursementCancellation` (82), `createOrUpdateTaxComponent` (75)

## trustt-platform-actor

- **APIs:** 473 (95 mutating, 378 read/inquiry)
- **Tables written:** 119 — `\`, `account_details`, `actor`, `actor__address__mapping`, `actor__contact_detail__mapping`, `actor__document__mapping`, `actor_account`, `actor_account_van`, `actor_reversible_status_change_details`, `address`, `address__contact_detail__mapping`, `address_geo_detail`, `address_geocoding_map`, `agent_custom_details` (+105 more)
- **APIs calling another service:** 75
- **Depends on:** `trustt-platform-accounting`, `trustt-platform-api-gateway`, `trustt-platform-approval`, `trustt-platform-authorization`, `trustt-platform-dms`, `trustt-platform-los`, `trustt-platform-masterdata-management`, `trustt-platform-notifications`, `trustt-platform-payments`, `trustt-platform-task`
- **Largest flows:** `createOrUpdateAgent` (328), `createOrUpdateEmployee` (223), `createOrUpdateAgentEmployee` (196), `createOrUpdateCorporateEmployee` (173), `createOrUpdateMeetingCenter` (119)

## trustt-platform-api-gateway

- **APIs:** 15 (4 mutating, 11 read/inquiry)
- **Tables written:** 12 — `\`, `address`, `address__contact_detail__mapping`, `client_key`, `contact_detail`, `hierarchy_element__entity__mapping`, `office`, `office__address__mapping`, `office_attribute`, `session`, `user__address__mapping`, `user_handle`
- **APIs calling another service:** 0
- **Largest flows:** `createOffice` (15), `createUser` (6), `getOfficeDetails` (6), `getCorporateHierarchyLevels` (4), `getOfficeList` (3)

## trustt-platform-approval

- **APIs:** 15 (9 mutating, 6 read/inquiry)
- **Tables written:** 3 — `application`, `application_attachment`, `draft_application`
- **APIs calling another service:** 6
- **Depends on:** `trustt-platform-actor`, `trustt-platform-authorization`, `trustt-platform-dms`, `trustt-platform-notifications`
- **Largest flows:** `rejectApplication` (15), `approveApplication` (13), `sendApplicationForClarification` (10), `getApplicationList` (9), `submitApplication` (7)

## trustt-platform-audit

- **APIs:** 7 (1 mutating, 6 read/inquiry)
- **Tables written:** 0
- **APIs calling another service:** 2
- **Depends on:** `trustt-platform-notifications`
- **Largest flows:** `getAuditEsDataByQuery` (2), `getAuditEsDataByUserStory` (2), `getApiResponseByStan` (1), `getAuditDetails` (1), `getAuditDetailsForUsers` (1)

## trustt-platform-authorization

- **APIs:** 27 (5 mutating, 22 read/inquiry)
- **Tables written:** 5 — `corporate__role__mapping`, `role`, `role_department`, `role_hierarchy`, `user__role__mapping`
- **APIs calling another service:** 4
- **Depends on:** `trustt-platform-actor`, `trustt-platform-approval`, `trustt-platform-notifications`
- **Largest flows:** `createOrUpdateRole` (64), `deleteRole` (20), `getRoleList` (7), `getRoleDetails` (6), `getPermissionList` (4)

## trustt-platform-batch

- **APIs:** 25 (7 mutating, 18 read/inquiry)
- **Tables written:** 6 — `BATCH_JOB_EXECUTION`, `batch_group`, `batch_job`, `batch_job_parameter`, `batch_schedule`, `file_upload`
- **APIs calling another service:** 2
- **Depends on:** `trustt-platform-approval`, `trustt-platform-authorization`
- **Largest flows:** `createOrUpdateBatchGroup` (4), `createOrUpdateBatchJob` (3), `createOrUpdateBatchSchedule` (2), `viewBulkBatchUploadFileStatus` (2), `bulkBatchSubmitApplication` (1)

## trustt-platform-dms

- **APIs:** 8 (2 mutating, 6 read/inquiry)
- **Tables written:** 2 — `document_master`, `file_master`
- **APIs calling another service:** 0
- **Largest flows:** `uploadDocument` (20), `downloadDocument` (4), `getDocumentDetails` (2), `mergeDocuments` (1), `validateDocuments` (1)

## trustt-platform-los

- **APIs:** 517 (144 mutating, 373 read/inquiry)
- **Tables written:** 110 — `aadhaar_redaction_status`, `aadhaar_ref_mapping`, `account_details`, `account_details_extension`, `activity_purchase_sales`, `activity_sub_category`, `atal_pension_yojana_details`, `borrower`, `borrower_reference`, `borrower_stability`, `business_activities`, `ckyc_file_details`, `credit_bureau_details`, `credit_bureau_existing_loan_details` (+96 more)
- **APIs calling another service:** 63
- **Depends on:** `trustt-platform-accounting`, `trustt-platform-actor`, `trustt-platform-authorization`, `trustt-platform-dms`, `trustt-platform-masterdata-management`, `trustt-platform-notifications`, `trustt-platform-task`
- **Largest flows:** `createOrUpdateMappedQuestionnaire` (31), `createOrUpdateQuestionnaireMaster` (24), `createOrUpdateBorrowerKycDetails` (17), `createOrUpdateLoanApp` (15), `submitCreditUnderwriting` (13)

## trustt-platform-masterdata-management

- **APIs:** 38 (5 mutating, 33 read/inquiry)
- **Tables written:** 3 — `code_master`, `code_master_details`, `configuration`
- **APIs calling another service:** 3
- **Depends on:** `trustt-platform-actor`, `trustt-platform-approval`
- **Largest flows:** `createOrUpdateMasterData` (116), `createOrUpdateConfiguration` (26), `deleteMasterData` (24), `getMasterDataDetails` (5), `getBranchGeoList` (3)

## trustt-platform-notifications

- **APIs:** 21 (4 mutating, 17 read/inquiry)
- **Tables written:** 3 — `app_notification_log`, `sms_log`, `user_fcm_details`
- **APIs calling another service:** 0
- **Largest flows:** `sendFCMNotification` (6), `updateTokensForTopic` (4), `fetchNotificationCode` (1), `generateOTP` (1), `getEmailTemplateDetails` (1)

## trustt-platform-payments

- **APIs:** 275 (51 mutating, 224 read/inquiry)
- **Tables written:** 49 — `actor__address__mapping`, `address`, `batch_denominations_recon_details`, `bulk_upload_file_details`, `cash_denominations_recon_details`, `cash_denominations_serial_numbers`, `cds_rectification_details`, `cds_rectification_details_history`, `collection`, `collection__sup_review_task_mapping`, `collection_activity`, `collection_attempt_activity_mapping`, `collection_attempt_history`, `collection_attempts` (+35 more)
- **APIs calling another service:** 28
- **Depends on:** `trustt-platform-accounting`, `trustt-platform-actor`, `trustt-platform-dms`, `trustt-platform-los`, `trustt-platform-task`
- **Largest flows:** `createOrUpdateRecordAttempt1` (28), `createOrUpdateRecordAttempt` (27), `doMfiCollections` (14), `fetchCollectionRecords` (9), `doMfiBranchCollection` (8)

## trustt-platform-reporting

- **APIs:** 119 (67 mutating, 52 read/inquiry)
- **Tables written:** 1 — `scheduled_reports_audit_data`
- **APIs calling another service:** 2
- **Depends on:** `trustt-platform-actor`, `trustt-platform-batch`
- **Largest flows:** `generateReport` (53), `cicMonthlyGroupLevelExtractJob` (2), `cicMonthlyMemberLevelExtractJob` (2), `creditProductivityExtractJob` (2), `generateAPYBaseNetDataExtractJob` (2)

## trustt-platform-task

- **APIs:** 52 (17 mutating, 35 read/inquiry)
- **Tables written:** 6 — `task`, `task_attributes`, `task_delegation`, `task_delegation_details`, `task_extension`, `task_type`
- **APIs calling another service:** 14
- **Depends on:** `trustt-platform-accounting`, `trustt-platform-actor`, `trustt-platform-authorization`, `trustt-platform-los`
- **Largest flows:** `createOrUpdateTask` (36), `createOrUpdateTaskMfi` (36), `deleteTask` (26), `getTaskList` (20), `deleteTaskMfi` (17)

