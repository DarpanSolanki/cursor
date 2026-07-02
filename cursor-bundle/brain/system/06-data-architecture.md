# 06 · Data architecture — schemas across services

> Each service owns its schema. There is **no shared schema** and no cross-service foreign keys at the DB level. Logical FKs (e.g. `loan_account.customer_id` → actor's `customer.id`) are enforced at the application layer only.

## Schemas at a glance

| Schema | Service | Notes |
|---|---|---|
| `mfi_los` | LOS | 130+ entities; loan applications, KYC, eligibility, group, document, dispatch |
| `mfi_accounting` | accounting (LMS) | Loan accounts, GL, transactions, EOD artefacts, mandates. Also Spring Batch meta-tables |
| `mfi_actor` | actor | Customers, employees, offices, hierarchy, users |
| `mfi_payments` | payments (LCS) | Collections, finnone+vymo sync tables, file staging |
| `mfi_batch` | batch | `batch_job`, `batch_schedule`, `batch_group`, `file_upload`, `master_file_type_config` |
| `mfi_approval` | approval | `draft_application`, `application`, `application_attachment`, `user_story` |
| `mfi_task` | task | `task`, `task_activity`, `workflow_master`, `tat_escalation_matrix`, `task_delegation*` |
| `mfi_audit` | audit | `request_log`, `response_log`, `external_service_details`, `telemetry_log` (+ ES index) |
| `mfi_masterdata` | masterdata | `code_master`, `code_master_details`, plus per-master tables (banks, branches, APY config) |
| `mfi_notifications` | notifications | `notification_message`, `code__notification_code__mapping`, `otp_config` |
| (single) | dms | `document_master`, `file_master`, `document_tags`, `sequence_generator` |
| `mfi_authorization` | authorization | `role`, `role_hierarchy`, `permission`, `role_permission_map`, `user_role_mapping`, `epic`, `feature`, `userstory`, `usecase`, `role_department` |
| `mfi_api_gateway` | api-gateway | `session`, `client`, `client_key`, `api_usecase_mapping`, `request_stan_log`, `request_log`, `response_log`, `request_forward`, `CallbackRequestResponseLog` |
| `platform_master` | initial-setup | tenant master + ~700 API definitions (read by gateway routing) |
| `mfi_reporting` | reporting (trustt-platform-reporting) | **All LMS reports & extracts read from here** — NOT from `mfi_accounting` live. ETL-populated `soa_*` snapshot tables + ~100 views. Lives in the **same DB instance** as `mfi_accounting`. See section below. |

## Cross-service logical FKs (enforced in code, not DB)

```
los.loan_app.customer_id           ──▶ actor.customer.id
los.loan_app.product_id            ──▶ accounting.loan_product.id
los.loan_app.disbursement_lan_id   ──▶ accounting.account.account_number  (after disbursement)
accounting.loan_account.customer_id ──▶ actor.customer.id
accounting.loan_account.office_id  ──▶ actor.office.id
accounting.account.parent_account_id ──▶ accounting.account.id  (SHG/JLG parent—child intra-schema)
payments.collection.loan_account_id ──▶ accounting.loan_account.id
payments.collection.customer_id     ──▶ actor.customer.id
payments.collection.employee_id     ──▶ actor.employee.id
task.task.<entity_id>              ──▶ depends on task_type (could be loan_app_id, loan_account_id, etc.)
approval.application.target_api_name + target_payload references arbitrary entity IDs
audit.request_log.client_ref_no    ──▶ caller's idempotency key (e.g. STAN)
gateway.api_usecase_mapping.api_name ──▶ initial-setup-seeded apiName (referenced everywhere)
```

## Per-service deep maps

- LMS / accounting tables: [`../accounting/09-data-model.md`](../accounting/09-data-model.md)
- LOS tables: [`../services/novopay-mfi-los.md`](../services/novopay-mfi-los.md) §"DB clusters"
- Payments tables: [`../services/novopay-platform-payments.md`](../services/novopay-platform-payments.md) §"DB clusters"
- Actor tables: [`../services/novopay-platform-actor.md`](../services/novopay-platform-actor.md) §"DB clusters"

## Reporting layer — `mfi_reporting` (check this before touching any transaction / loan field)

**All LMS reports and file extracts depend on the `mfi_reporting` schema** — they do NOT query `mfi_accounting` live. Facts for impact analysis:

- `mfi_reporting` lives in the **same DB instance** as `mfi_accounting`. It holds ETL-populated `soa_*` snapshot tables — `soa_loan_account_billing_details`, `soa_loan_account_txn_details`, `soa_loan_account_payment_details`, `soa_enach_presentation_details`, `soa_si_presentation_details` — plus ~100 views (SOA report, eNACH-return, cheque-bounce, APY, NRLM, WL disbursement-advice extracts).
- The `soa_*` billing/txn tables carry only `reference_number` (system-generated hex); **no `client_reference_number` column** — a caller-supplied CRN cannot land there. The only `client_reference_number` in `mfi_reporting` is `soa_loan_account_payment_details` (`varchar(128)`).
- A transaction that writes no `loan_account_billing_details` row in `mfi_accounting` (e.g. the DFC partial-cycle force-bill) never enters the reporting ETL — invisible to the SOA report.
- **Rule:** any change to a transaction/loan field MUST be checked against `mfi_reporting` (tables AND views). Run `information_schema` view/column queries with **no schema filter** so all schemas (`mfi_accounting`, `mfi_reporting`, `mfi_los`, …) are covered.

## Read-replica / analytical patterns

- **RBI ADF tasklets** call accounting / LOS / actor service APIs directly. For high-volume extracts, the `mfi_reporting` `soa_*` tables (above) are the source.
- **Audit ES index** is the analytical store for "who did what when" — backed by Kafka → audit service → ES write.

## Migrations

- Every schema's DDL + seed data is owned by `novopay-platform-initial-setup` (Flyway). See [`../services/novopay-platform-initial-setup.md`](../services/novopay-platform-initial-setup.md).
- **Online schema changes are coordinated through initial-setup** — services don't `flyway:migrate` themselves.

## DB engines

- All services use **PostgreSQL / YugabyteDB** (YB is wire-compatible with PG).
- **Spring Batch meta-tables** (`BATCH_JOB_INSTANCE`, `BATCH_JOB_EXECUTION`, `BATCH_STEP_EXECUTION`) live in the **target service's** datasource (typically `mfi_accounting`). Don't conflate with `mfi_batch.batch_job` (the registry in the batch service).

## Tenant model

- Single cluster, multi-schema per tenant: schema name = `<service>` for the primary tenant, `<service>_<tenant>` (or similar) for additional tenants. Resolved by the data source per ThreadLocalContext tenant.
- Per-tenant initial-setup directories (`flyway/sli/<service>/sql/<tenant>/`) define what's loaded.
- See [`10-environments-config.md`](10-environments-config.md) for tenant resolution + config drift.
