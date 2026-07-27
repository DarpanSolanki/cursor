# `novopay-platform-actor` — Mini-CRM (Customer / Employee / Office / Hierarchy / User)

> "Actor" is anyone or anything the platform tracks: customers, employees, corporates, agents, insurance providers, admins, even logical groups. This service is the **single source of truth** for: customer KYC + onboarding, employee + role + hierarchy, office + geography (state→district→VTC→hamlet), user authentication, meeting-centre / SHG-group masters, and portfolio transfers.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.actor` |
| DB schema | `mfi_actor` |
| Repo | [`novopay-platform-actor/`](../../novopay-platform-actor/) |
| Service CLAUDE.md | [`trustt-platform-actor/CLAUDE.md`](../../trustt-platform-actor/CLAUDE.md) |

## API surface — orchestration XMLs (29 files, ~33 500 lines)

Multi-tenant heavy. Per-tenant XML overrides plus the MFI core XML:

| XML | Lines | Domain |
|---|---:|---|
| `orc_mfi.xml` | 8 637 | MFI core: customers, employees, meeting centres, VTC, work areas, promo codes, hierarchy, bulk jobs |
| `ServiceOrchestrationXML.xml` | 4 765 | Generic CRUD: employee/office/user/device/hierarchy/inventory + auth |
| `orc_mfi2.xml` | 2 691 | MFI cont.: cash limits, village mappings, collections, portfolio transfer (40 Requests) |
| `orc_collections.xml` | 1 632 | Collection allocation: primary/secondary, rules, clusters, eligibility |
| `idfcp_corporate_orc_xml.xml`, `idfcp_agent_orc_xml.xml`, `idfcp_employee_orc_xml.xml`, `idfcp_agent_employee_orc_xml.xml` | 1 581 / 1 360 / 1 007 / 1 023 | IDFCP tenant overlays |
| `product_*_orc.xml` (5 files) | 868–1 397 ea. | Product tenant: customer / corporate / agent / employee flows |
| `waas_*_orc.xml` (5 files) | 176–763 ea. | WAAS tenant: customer / eKYC / corporate / card / login |
| `bp_*.xml` (6 files) | 12–409 ea. | BP tenant: customer / login / card / corporate / batch |
| `insurance_orc.xml` | 289 | Insurance provider ops |
| `fk_orc.xml`, `nl_agent_lending.xml`, `ServiceOrchestrationXML_idfc.xml` | 207 / 23 / 16 | Other tenants |

Top 40 Request names from the core XMLs:
`createOrUpdateEmployee`, `getEmployeeList`, `getEmployeeDetails`, `login`, `logout`, `agentLogin`, `createOrUpdateOffice`, `getOfficeDetails`, `getOfficeList`, `createUser`, `deleteUser`, `getUserList`, `getUserDetails`, `getParentHierarchyList`, `createOrUpdateHierarchyElement`, `getHierarchyLevels`, `getChildHierarchyElements`, `getVtcListForOfficeId`, `performInternalDedupe`, `getCustomerDetails`, `createMfiCustomer`, `updateMFICustomerDetails`, `createOrUpdateMeetingCenter`, `getListOfMeetingCenters`, `allocateMeetingCenter`, `reallocateMeetingCenter`, `getMeetingCenterDetails`, `registerDevice`, `setAuthValue`, `forgotPassword`, `changePassword`, `getDeviceList`, `deleteDevice`, `verifyUserHandle`, `getEncryptionKey`, `forgotPin`, `forgotAuthValue`, `deleteOffice`, `deleteEmployee`, `deleteCorporate`, `createOrUpdateDevice`.

## Kafka

Producer: `producer_id_actor`.

| Consumer bean | Topic prefix | Purpose |
|---|---|---|
| `posidexInboundActorConsumer` | `posidex_actor_inbound_` | Posidex inbound payloads |
| `sessionActivityLoginConsumer` | `session_activity_login_` | Login events |
| `sessionActivityLogoutConsumer` | `session_activity_logout` | Logout events |
| `updateCustomerLoanDetailsConsumer` | `update_customer_loan_details` | Customer/loan sync |

## Outbound HTTP

- authorization (role/permission validation)
- masterdata (state/district, code lookups via `MasterDataUtil`)
- notifications (SMS / email / push)
- dms (`DmsUtilActor` — KYC documents)
- approval (maker-checker on employee/office updates via `ApprovalCommonUtility`)
- Superset (dashboard guest tokens — `GetGuestTokenFromSupersetProcessor`)
- Google reCAPTCHA (login validation)
- External eKYC providers (Equitas, Sarvatra) and retail/collection integrations

## Who calls actor (inbound)

**Everyone.** Actor is the most-called service in the platform.

- **LOS** — customer/employee/office/hierarchy for every loan application
- **Accounting** — `getUserDetails`, `getOfficeDetails`, `getCustomerDetails`, `getRoleDetailsByUserId`, `createActorAccountDetails` per Request
- **Payments** — `getEmployeeData`, `getCustomerDetailsForCollection`, `getOfficeDetails`, `getBasicGroupDetails`, `getEmployeeHierarchyDetails`
- **Task** — hierarchy + employee for assignment / delegation
- **API Gateway** — user authentication, session, role lookup
- **Batch jobs** — portfolio transfer, employee dormancy, VTC dumps

## DB clusters

| Cluster | Tables |
|---|---|
| Core actors | `actor`, `customer`, `employee`, `corporate`, `agent`(`partner`/`details`/`custom`) |
| Users + auth | `user`, `user_auth`, `user_auth_type`, `key`, `user_login_history` |
| Addresses + contacts | `address`, `actor__address__mapping`, `contact_detail`, `actor__contact_detail__mapping` |
| Office + geography | `office`, `office__serviceable_products`, `office_vtc_mapping_history`, `state_vtc_hierarchy_dump`, `hamlets`, `vtc_hamlets_mapping` |
| Hierarchy | `hierarchy_template`, `hierarchy_level`, `hierarchy_element` |
| Employee extended | `employee__serviceable_offices`, `employee__serviceable_products`, `employee_extension`, `employee_work_area`, `dsa_employee`, `branch_employee_status_matrix` |
| Meeting + collections | `meeting_center`, `meeting_center_allocation`, `meeting_center_allocation_history`, `promo_code`, `promo_code_mapping` |
| Portfolio transfer | `portfolio_transfer_request`, `portfolio_transfer_request_ext`, `portfolio_transfer_request_history`, `portfolio_transfer_execution_history` |
| Bulk staging | `file_staging_office_upsert`, `file_staging_ucic_update`, `file_staging_behavior_score`, `file_staging_employee_location_update`, `file_staging_employee_target`, `file_staging_hdfc_hrms`, `file_staging_state_district_master`, `file_staging_village_creation`, `file_staging_vrm_category` |
| Customer extended | `customer_onboard_history`, `customer_behaviour_score`, `customer_loan_details`, `loan_details_customer` |

## Caching (Redis)

| Index | What | Notes |
|---|---|---|
| 3 (ACTOR) | Actor / employee / office / user details, portfolio transfer context | Tenant prefix; per-key TTL or on update |
| 2 (NOTIFICATION) | Notification message templates | Per template validity |
| 0 (DEFAULT) | Superset guest / auth tokens | Token validity period |

## Concepts owned (downstream services depend on these)

- **Use-case codes** — every accounting Request resolves a `getUseCaseDetails` call against actor for codes like `GENL-LEDG-UC001`, `INTL-ACCT-DEFN`, etc. The use-case master defines maker-checker behaviour and notification routing.
- **Role + permission** — role is mapped to permissions; validated via authorization service. Hierarchy resolves to delegation / approval routing.
- **Function code** — all Requests pattern-validate `function_code` against tenant config.
- **Cash limit** — `employee_cash_limit`, `employee_cash_in_hand` enforce per-employee daily collection limits.
- **Hierarchy** — employee reporting structure (parent_id chains); used everywhere for delegation and visibility.

## Known gotchas

- **29 orchestration XMLs** — Request resolution depends on tenant. The same Request name may be defined in multiple XMLs with different bean lists; always check tenant context first.
- **Portfolio transfer** is split across actor + accounting + LOS — see [`../platform/cross-service-transactions.md`](../platform/cross-service-transactions.md).
- **Login flows** route reCAPTCHA → external Google API. Outage there blocks login.
