# Production Flyway — manual DDL (STANDING)

**Production does not run initial-setup Flyway automatically.** Every migration that ships to prod must include:

1. **DDL** — execute the SQL from the Flyway file on the target schema.
2. **`flyway_schema_history` INSERT** — register version with **correct Flyway checksum** (not NULL).
3. **Pre or Post deployment** — JIRA field + release Special notes.

## Checksum (mandatory)

Flyway **5.2.4** (novopay initial-setup `flyway/lib/community`) — checksum must match the migration file bytes or Flyway validate will fail on next run.

```bash
bash scripts/bin/flyway-checksum.sh novopay-platform-initial-setup/flyway/sli/accounting/sql/product/V000198__....sql
# Example output: -1807997428
```

Deploy pack generator auto-computes checksum:

```bash
bash scripts/bin/flyway-prod-deploy-pack.sh <Vxxxx.sql> --out scripts/sql/deploy/prod_pre_Vxxxx_....sql
```

**Never** use `checksum NULL` in production INSERT unless DBA explicitly confirms out-of-band.

## Agent rule

- **Never ask** whether prod uses manual DDL — **always yes**.
- **Never say** "run Flyway on prod" without DDL + INSERT + checksum.
- **Always generate** deploy pack for every new `Vxxxx__*.sql` in a release.

## Pre vs post

| Pre | Post |
|-----|------|
| CREATE INDEX, CREATE TABLE, ALTER add column | INSERT/UPDATE data backfill after deploy |
| Required before new app handles traffic | Safe only after new code is live |

## INSERT template

```sql
INSERT INTO mfi_accounting.flyway_schema_history
(installed_rank, version, description, type, script, checksum, installed_by, installed_on, execution_time, success)
VALUES
((SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM mfi_accounting.flyway_schema_history),
 '000198', 'dfisd staging composite indexes', 'SQL', 'product/V000198__dfisd_staging_composite_indexes.sql',
 -1807997428, 'yugabyte', NOW(), 0, true);
```

Rule: `.cursor/rules/20-ship-gates.mdc`  
Tools: `scripts/bin/flyway-checksum.sh`, `scripts/bin/flyway-prod-deploy-pack.sh`
