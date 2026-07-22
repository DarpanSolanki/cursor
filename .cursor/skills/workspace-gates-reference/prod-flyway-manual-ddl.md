<!-- VERBATIM archive of former alwaysApply `.cursor/rules/prod-flyway-manual-ddl.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Production Flyway — manual DDL path (STANDING)

**Darpan production constraint (mandatory):** Initial-setup Flyway migrations **do not auto-run on production**. DBAs run scripts manually.

## Every schema change release must deliver

1. **DDL** — the actual `CREATE` / `ALTER` / `INDEX` statements (from the Flyway file body).
2. **`flyway_schema_history` INSERT** — register the migration so Flyway stays aligned with prod.
3. **Timing** — label **Pre deployment** or **Post deployment** on JIRA + release Special notes.

**Do not** tell release/DBA to "run Flyway V00xxx on prod" without the INSERT + DDL pack.

## Agent workflow

| Step | Action |
|------|--------|
| 1 | Add `Vxxxx__*.sql` in `trustt-platform-initial-setup` (source of truth for dev/QA Flyway) |
| 2 | Generate prod pack: `bash scripts/bin/flyway-prod-deploy-pack.sh <flyway.sql> --out scripts/sql/deploy/prod_<pre\|post>_Vxxxx_<short>.sql` |
| 3 | Put DDL + INSERT in JIRA **Pre/Post deployment** field and release **Special notes** |
| 4 | QA/local may still use Flyway or `scripts/sql/setup/` hot-apply — prod uses the pack |

Generator: `scripts/lib/flyway_prod_deploy_pack.py`  
Memory: `cursor-bundle/memory/reference_prod_flyway_manual_ddl.md`

## Pre vs post

| Pre deployment | Post deployment |
|----------------|-----------------|
| `CREATE INDEX`, `CREATE TABLE`, `ALTER TABLE` add column/index | Data `INSERT`/`UPDATE` backfill after code is live |
| Schema required **before** new app version processes traffic | One-time correction when old code tolerates missing change |
| **Default for indexes** on batch hot paths | Cleanup / seed rows tied to new code behaviour |

When unsure: indexes and additive DDL → **pre**; data-only migrations → **post**.

## `flyway_schema_history` INSERT shape (per schema)

```sql
INSERT INTO mfi_accounting.flyway_schema_history
(installed_rank, version, description, type, script, checksum, installed_by, installed_on, execution_time, success)
VALUES
((SELECT COALESCE(MAX(installed_rank), 0) + 1 FROM mfi_accounting.flyway_schema_history),
 '000198', 'dfisd staging composite indexes', 'SQL', 'product/V000198__dfisd_staging_composite_indexes.sql',
 NULL, 'yugabyte', NOW(), 0, true);
```

- **version** — six-digit style from filename (`V000198` → `000198`), match existing rows in that schema.
- **script** — path under `product/` as stored in history (verify on target env).
- **checksum** — `NULL` unless DBA requires Flyway checksum match.

## Never ask again

Agents must **not** ask whether prod uses manual DDL — it does. Auto-generate the deploy pack for every new Flyway migration in a release.

## Pair with

- `.cursor/skills/release-details/SKILL.md` — Special notes SQL
- `.cursor/skills/jira-fix-update/SKILL.md` — `customfield_11336` Pre/Post
- `.cursor/skills/query-index-perf-gate/SKILL.md` — index Flyway + prod pack
