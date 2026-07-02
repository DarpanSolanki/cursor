# Production DB indexes baseline (STANDING)

**Canonical file:** `cursor-bundle/reference/db/prod-indexes-baseline.csv`  
**Manifest:** `cursor-bundle/reference/db/prod-indexes-manifest.json`  
**Snapshot:** 2026-06-19 (production export, 2432 index rows)

## Agent rule (do not violate)

- **Always** use the baseline CSV for **production index inventory** when auditing `@Query`, batch reader WHERE, or proposing new indexes.
- **Do NOT** ask Darpan for prod index exports on every task — this snapshot is authoritative until he provides a replacement file.
- **Live DB** (`db-qaN.sh`, `db-local.sh`) is for **EXPLAIN**, row counts, and verifying whether QA/local has applied a pending Flyway index — not for guessing prod index state.

## Quick lookup

```bash
bash scripts/bin/query-index-perf-audit.sh --prod-lookup mfi_accounting.death_foreclosure_insurance_staging_details
bash scripts/bin/query-index-perf-audit.sh --group dcf_insurance_reupload --prod-baseline
bash scripts/bin/query-index-perf-audit.sh --group dcf_insurance_reupload --db qa4   # + EXPLAIN on QA
```

## Refresh (when user provides new CSV)

1. Overwrite `cursor-bundle/reference/db/prod-indexes-baseline.csv`
2. Update `prod-indexes-manifest.json` (`snapshot_date`, `source_file`, `row_count`)
3. Append `.cursor/changelog.md` kb-only row

Skill: `.cursor/skills/query-index-perf-gate/SKILL.md`
