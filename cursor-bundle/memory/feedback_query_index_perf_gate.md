---
name: feedback_query_index_perf_gate
description: "New @Query / batch reader changes: prod index baseline CSV first, then live EXPLAIN"
metadata:
  node_type: memory
  type: feedback
---

When a fix adds native SQL (`@Query`, `@Modifying`, batch reader WHERE):

1. **Prod baseline (mandatory, no DB):** `bash scripts/bin/query-index-perf-audit.sh --prod-baseline` or `--prod-lookup schema.table` — uses `cursor-bundle/reference/db/prod-indexes-baseline.csv` (2026-06-19 snapshot). **Do not ask user for prod index export** unless they say they are replacing the snapshot.
2. **Live EXPLAIN (when env available):** `bash scripts/bin/query-index-perf-audit.sh --group <profile> --db qa4 --prod-baseline`
3. Report: prod `IN_PROD` / `NOT_IN_PROD`, seq scan vs index scan, row count, per-item multiplier
4. WARN at small table size is OK; FAIL at high cost / production row count with PK-only prod baseline
5. L2 index recommendation in release Special notes — L0 hot-apply SQL when prod baseline shows `NOT_IN_PROD`

Skill: `.cursor/skills/query-index-perf-gate/SKILL.md`  
Memory: `cursor-bundle/memory/reference_prod_db_indexes_baseline.md`
