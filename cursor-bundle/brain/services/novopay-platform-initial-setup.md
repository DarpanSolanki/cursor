# `trustt-platform-initial-setup` — Bootstrap (Flyway, not a service)

> **Not a Spring service** — a bundled Flyway CLI invoked from a shell script. It bootstraps service schemas and pre-loads platform/master data.

## Identity

| Field | Value |
|---|---|
| Type | Bundled Flyway Community CLI 5.2.4 |
| Repo | `trustt-platform-initial-setup/` |
| Release branch | Match the service train, e.g. `mfi_integration_v3.7.1` |
| Local target | `flyway/conf/localhost.conf` → `127.0.0.1:5433/yugabyte` |

## Local runbook

`trustt-platform-initial-setup` is a read-only input to local bootstrap work: fetch/sync it, but do not edit, commit, or push it from this workspace workstream. Fetch both remotes separately and align to the fresh upstream train only when the working tree is clean and no origin-only work would be lost.

```bash
cd /home/darpan/Documents/sliProd/trustt-platform-initial-setup
git fetch origin
git fetch upstream
git checkout -B mfi_integration_v3.7.1 upstream/mfi_integration_v3.7.1

cd /home/darpan/Documents/sliProd
bash scripts/bin/initial-setup-local.sh accounting-core
```

The workspace wrapper invokes the untouched `flyway/localhost.sh <service>` one service at a time. It verifies the JDBC target is local `127.0.0.1|localhost:5433`, refuses a modified runner, detects duplicate versions before Flyway starts, continues independent services after a failure, and never calls `all`.

Direct runner usage remains:

```bash
cd trustt-platform-initial-setup/flyway
sh localhost.sh accounting
```

The argument selects `conf/<service>.conf`; that file defines one schema and its SQL locations. Flyway history is per schema. Newer local schemas use `flyway_schema_history`; older schemas such as masterdata, authorization, gateway, and approval still use `schema_version`. Flyway 5.2.4 detects and uses that legacy table with a warning; it does not rename it.

For each service, `localhost.sh` executes:

1. `./flyway -outOfOrder=true repair`
2. `./flyway -outOfOrder=true migrate`

The upstream script uses `set -e`; `all` stops on the first failing service. For dependency-led local work, do not use `all`: unrelated schemas (currently masterdata and notifications) contain duplicate versions and can prevent later services from running.

## Dependency-led accounting schema matrix (verified 2026-07-17)

| Service | Why accounting needs it | Migrate |
|---|---|---|
| `masterdata` | Codes, product/configuration, business date; documented accounting SPOF | **Yes (core)** — currently blocked on GAP-077 in untouched upstream |
| `actor` | Employee, office, customer, and group APIs used by accounting | **Yes (core)** |
| `authorization` | Permission checks for gateway and protected accounting flows | **Yes (core)** |
| `accounting` | Ledger, loans, batches, and financial state | **Yes (core)** |
| `batch` | Scheduler/job execution for accounting jobs | **Yes (core)** |
| `gateway` | External HTTP ingress only; direct accounting harness bypasses it | Conditional |
| `dms` | Document-linked flows only | Conditional |
| `approval` | Maker-checker flows only | Conditional |
| `payments` | Collection/allocation flows only | Conditional |
| `los` | Origination/disbursement lifecycle, not required for accounting-only bootstrap | Conditional |
| reporting/notifications/consents/platform_master | Not required for the accounting-core local process | No unless the tested flow proves the dependency |

Local run status on 2026-07-17: accounting, actor, authorization, batch, dms, gateway, and approval were up to date; masterdata was reconciled locally to `9000861` during investigation, but the untouched upstream runner still cannot re-run it because of GAP-077. No DPI regression or JIRA action was performed.

## Safe local reconciliation

- **Genuinely missing DDL with a migration:** let Flyway execute it.
- **DDL/data already fully present but history missing:** prove every statement/effect in that exact migration already exists, then add the exact row to that schema's actual history table (`flyway_schema_history` or legacy `schema_version`) and rerun. Do not mark a partially applied migration successful.
- **Transactional Yugabyte failure after data cleanup:** apply the exact migration SQL locally through `scripts/bin/db-local-write.sh`; verify every object/data effect; only then record that exact migration in history. The next `localhost.sh` repair normalizes its checksum.
- **No migration file exists:** never invent a history version. Use an idempotent `scripts/sql/setup/local_setup_*.sql` only for local reproducibility and raise a release gap for a real Flyway migration.
- **Duplicate migration version:** do not edit or rename tracked initial-setup files locally. Stop that service, run independent services through the workspace wrapper, and raise/follow the release gap. A history insert cannot fix duplicate-version scan failure.

Current 3.7.1 example: accounting code requires `mfi_accounting.loan_account.dpi_suspense_amount`, but fresh upstream `e4ade8c3f8` has no Flyway migration for it. Local setup is `scripts/sql/setup/local_setup_dpi_suspense_amount.sql`; QA/prod still require a proper initial-setup migration.

Current 3.7.1 duplicate-version gap (GAP-077): masterdata has two `V000119` files and two `V000120` files; notifications has two `V9000423` files. Flyway 5.2.4 aborts before migration discovery. These require release-owned version renumbering upstream, not a local initial-setup commit.

## Production deployment

Initial-setup Flyway does not auto-run in production. Every schema release must provide the DDL plus the matching `flyway_schema_history` insert in a manual pre/post deployment pack; see `.cursor/rules/20-ship-gates.mdc`.

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
2. **Repair runs automatically before migrate** — it repairs schema-history metadata; it does not create missing application columns.
3. **Per-tenant directories** — multi-tenant deployments need explicit `<tenant>` directories per service.
4. **API-master SQL is foundational** — a missing row here means the gateway cannot route the apiName at all (404).
