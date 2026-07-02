# Runbook — Tenant bootstrap / new API not routable

## Symptoms

- New tenant onboarding: services start but Requests 404.
- New API added in some service but gateway returns "no routing".
- Schema missing on a new tenant — entity reads fail with table-not-found.
- Initial-setup script run but data not visible.

## Where bootstrap data lives

| Data | Source | Notes |
|---|---|---|
| Tenant master | `flyway/sli/platform_master/sql/V000003__tenant_master_data.sql` | One-time per cluster |
| API master (~700 apiNames) | `flyway/sli/platform_master/sql/V000005__api_master_data.sql` | Maps apiName → service id (gateway routing) |
| Per-service schema + master data | `flyway/sli/<service>/sql/<tenant>/V*.sql` | Per-tenant directories |
| Roles, permissions, usecases | `flyway/sli/authorization/sql/<tenant>/` | per-tenant |
| Employee, office, user mappings | `flyway/sli/actor/sql/<tenant>/` | per-tenant |
| GL chart, products, transaction rules | `flyway/sli/accounting/sql/<tenant>/` | per-tenant |

## Decision tree

### A. New tenant, all Requests 404

1. **Did initial-setup run for this tenant?**
   ```bash
   sh localhost.sh all   # in novopay-platform-initial-setup
   ```
2. Check `platform_master.tenant_master` — is the tenant row present?
3. Check service-side `api_master_data` — did per-service init run?
4. Check gateway's tenant resolution config — is the new tenant code recognised?

### B. Existing tenant, new Request 404

The Request name was added to the orchestration XML in service X, but:
1. **Missing `api_master_data` row** for the new apiName → gateway can't resolve which service owns it.
   - Add a V file under `platform_master/` Flyway with the new apiName + service id.
   - Run initial-setup.
2. **Missing `api_usecase_mapping`** in gateway → permission check fails.
   - Add the mapping (apiName → usecase code).
3. **Missing `usecase` + `permission`** in authorization for the new use case.

### C. New Request routable but throws "table not found"

Schema migration didn't run for that service / tenant. Run:
```bash
sh localhost.sh <service>
```

### D. Schema-history mismatch / Flyway repair needed

Initial-setup runs with `enableRepair=true` ([`README.md:191`](../../novopay-platform-initial-setup/README.md)). If Flyway complains about checksum mismatch or out-of-order versions:
1. Check `flyway_schema_history` table on the affected schema.
2. Manual repair via the Flyway CLI or re-run initial-setup with `enableRepair=true`.
3. Never modify `flyway_schema_history` directly.

### E. New role / permission not effective

After adding a new role/permission/usecase:
1. Re-run `sh localhost.sh authorization`.
2. Have the user log out and back in (session cache).
3. Verify `mfi_authorization.role_permission_map` row.
4. Verify gateway-side `api_usecase_mapping` row exists for any new Requests in the use-case.

### F. New batch job not firing

After adding a `BatchJob`:
1. Insert a row in `mfi_batch.batch_job` with `name = "<RequestName>"`, `version`, `code`, `status='ACTIVE'`.
2. Insert a `mfi_batch.batch_schedule` row with cron + reference.
3. Restart the batch service or wait for `AutoScheduler` reload.
4. Verify by `getBatchScheduleList`.

## Cross-tenant verification checklist

For a healthy tenant, expect:
- [ ] `platform_master.tenant_master` row present
- [ ] `mfi_<service>` schemas exist for all 14 backend services
- [ ] `api_master_data` populated (~700 rows minimum for MFI tenant)
- [ ] `api_usecase_mapping` populated (in gateway)
- [ ] `role`, `permission`, `usecase` populated (in authorization)
- [ ] `office`, `employee`, `user` seeded (in actor)
- [ ] `general_ledger`, `internal_account_definition`, `transaction_catalogue`, `placeholder_master`, `transaction_accounting_rule`, `product_transaction_catalogue_placeholder` seeded (in accounting)
- [ ] `loan_product` + `product_scheme` configured (in accounting)
- [ ] `batch_job` rows present for EOD/BOD aggregators

## Code anchors

- Initial-setup README: [`novopay-platform-initial-setup/README.md`](../../novopay-platform-initial-setup/README.md)
- API master data: [`flyway/sli/platform_master/sql/V000005__api_master_data.sql`](../../novopay-platform-initial-setup/flyway/sli/platform_master/sql/V000005__api_master_data.sql)
- Tenant master: [`flyway/sli/platform_master/sql/V000003__tenant_master_data.sql`](../../novopay-platform-initial-setup/flyway/sli/platform_master/sql/V000003__tenant_master_data.sql)

## Related

- Initial-setup service brain: [`../services/novopay-platform-initial-setup.md`](../services/novopay-platform-initial-setup.md)
- API gateway brain (routing): [`../services/novopay-platform-api-gateway.md`](../services/novopay-platform-api-gateway.md)
- Environment / tenant model: [`../system/10-environments-config.md`](../system/10-environments-config.md)
