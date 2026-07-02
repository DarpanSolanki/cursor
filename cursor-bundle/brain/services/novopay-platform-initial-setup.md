# `novopay-platform-initial-setup` — Bootstrap (Flyway, not a service)

> **Not a Spring service** — a Flyway-based migration runner invoked from a shell script. Bootstraps every tenant's schemas across all platform services and pre-loads the global master data: tenant master, ~700 API definitions, service registry, GL chart, products, roles, permissions, employee hierarchies.

## Identity

| Field | Value |
|---|---|
| Type | Flyway migration runner (CLI) |
| Repo | [`novopay-platform-initial-setup/`](../../novopay-platform-initial-setup/) |
| Service CLAUDE.md | [`novopay-platform-initial-setup/CLAUDE.md`](../../novopay-platform-initial-setup/CLAUDE.md) |
| README | [`novopay-platform-initial-setup/README.md`](../../novopay-platform-initial-setup/README.md) |

## How it runs

Centralised CLI:
```bash
sh localhost.sh <service>     # e.g. sh localhost.sh authorization
sh localhost.sh all           # all services for this tenant
```

Internally executes `java -jar flyway-migrator.jar service=<service> path=<path_to_sql> enableRepair=true`.

## What lives where

```
flyway/sli/
├── platform_master/           ← global, runs ONCE per cluster
│   sql/
│     V000003__tenant_master_data.sql       Tenant master (mfi)
│     V000005__api_master_data.sql          ~700 API definitions: apiName + service binding
│
├── authorization/sql/mfi/     ← tenant-specific roles, permissions, epics, features, userstories, usecases
├── actor/sql/mfi/             ← employee data, office hierarchy, user mappings
├── accounting/sql/mfi/        ← schema + master data: products, GL, transaction rules
├── los/sql/mfi/
├── payments/sql/mfi/
├── dms/sql/mfi/
├── ...                        ← one per service
```

## What gets pre-loaded

- **Tenant master record** (MFI)
- **API catalogue** — ~700 apiNames each mapped to a service id (`createOrUpdateOffice`, `login`, `getRoleDetailsByUserId`, `postTransaction`, etc.). This is the data behind `api_usecase_mapping` in the gateway.
- **Roles + permissions** for core workflows (Loan Officer, Credit Underwriter, Branch Manager, etc.)
- **GL chart + account templates** (Savings, Checking)
- **Product schemes + pricing configs**
- **Employee hierarchies + office structures**
- **User-office mappings + role assignments**

## When you'll touch this

- **Onboarding a new tenant** — add per-service tenant SQL under `flyway/sli/<service>/sql/<tenant>/`. Run the centralised script.
- **Adding a new Request** — must add an entry to `api_master_data.sql` (or follow-up V0xxx file) so the gateway can route to it.
- **Adding a new role/permission/usecase** — V file under `flyway/sli/authorization/sql/<tenant>/`.
- **Schema migration on any service** — add a versioned V file under that service's `flyway/sli/<service>/sql/<tenant>/`.

## Known gotchas

1. **It is not a runtime service** — there's no `Application.java` to start. Operating "initial setup is down" means the script never ran, not that a process crashed.
2. **`enableRepair=true`** is enabled — be careful with rollbacks; Flyway repair re-aligns the schema-history table.
3. **Per-tenant directories** — multi-tenant deployments need explicit `<tenant>` directories per service.
4. **API-master SQL is foundational** — a missing row here means the gateway cannot route the apiName at all (404).
