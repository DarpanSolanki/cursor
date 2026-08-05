---
name: query-index-perf-gate
description: >-
  Mandatory for native SQL / batch WHERE changes: prod index baseline, full query matrix,
  best-solution ship bar on improvements (code + Flyway + cross-service + poison guards),
  live EXPLAIN when env available.
triggers:
  - @Query
  - nativeQuery
  - batch reader WHERE
  - repository index
  - query performance
  - prod indexes
  - improvement
  - best solution
requires:
  - reuse-queries-java-filter
reads:
  - cursor-bundle/reference/db/prod-indexes-manifest.json
  - cursor-bundle/memory/reference_prod_db_indexes_baseline.md
  - cursor-bundle/memory/feedback_enhancement_all_fronts.md
  - .cursor/rules/20-ship-gates.mdc
  - .cursor/rules/10-quality-gates.mdc
  - scripts/lib/query_index_perf_audit.py
  - scripts/lib/prod_index_baseline.py
writes: []
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `@Query`, `nativeQuery`, `batch reader WHERE`, `repository index`, `query performance`, `prod indexes`, `improvement`, `best solution`
- **requires:** `reuse-queries-java-filter`
- **reads:** `cursor-bundle/reference/db/prod-indexes-manifest.json`, `cursor-bundle/memory/reference_prod_db_indexes_baseline.md`, `cursor-bundle/memory/feedback_enhancement_all_fronts.md`, `.cursor/rules/20-ship-gates.mdc`, `.cursor/rules/10-quality-gates.mdc`, `scripts/lib/query_index_perf_audit.py`, `scripts/lib/prod_index_baseline.py`
- **writes:** []

# Query index + performance gate

Use when a fix adds or changes **native SQL** (`@Query`, batch reader WHERE, `@Modifying` UPDATE).

## Mode — pick before designing the fix

| Mode | When | Ship bar |
|------|------|----------|
| **Fire** | Prod broken now; hours matter | L0 alone OK (guard, hot-apply SQL) — document L1 follow-up |
| **Improvement** | Rework, enhancement, planned release, user asks for best fix | **Best solution only** — see checklist below; **do not** close with L0-only |

**Improvement = default** for SDCP rework, batch reliability, cross-service bugs, and any task where the user says *fix it properly / platform-wise / best way*.

## Improvement ship bar (best solution — all required unless N/A)

When mode = **Improvement**, ship **one coherent release**, not a symptom patch:

| # | Platform front | Required |
|---|----------------|----------|
| 1 | **Root cause** | Break callback loop / lock / partial commit — not timeout retry |
| 2 | **Cross-service contract** | Additive flag or EC key; deploy **paired services** together |
| 3 | **Transaction boundaries** | Independent commits where batch + HTTP callback caused circular lock (`REQUIRES_NEW` on claim/commit slices) |
| 4 | **Poison / partial state** | Code guard for dirty prod rows **and** idempotent replay path |
| 5 | **Batch isolation** | Per-record try/catch; reader excludes in-flight terminal statuses |
| 6 | **Query matrix** | Every `@Query`/reader on the table → `scripts/lib/*_query_index_matrix.json` |
| 7 | **Indexes** | Flyway migration + ops hot-apply script; **three indexes max per conflicting predicate set** — not one mega-index |
| 8 | **Prod baseline audit** | Layer 1 mandatory (`--prod-baseline`); prove `NOT_IN_PROD` before proposing |
| 9 | **Live EXPLAIN** | Layer 2 on QA when env available |
| 10 | **Hot-path scan** | N+1, per-loop duplicate fetch — fix significant wins in same PR |
| 11 | **Regression** | Registry audit case or sibling batch path grep |

**Reject as incomplete:** code-only fix with seq scan on PK-only prod table and no Flyway; cross-service change without paired deploy note; "QA has 120 rows so seq scan is fine" without prod baseline + growth note.

## Standing rule — prod index truth

**Do not ask the user for prod index exports.** Use the canonical snapshot until they explicitly provide a replacement CSV:

| Artifact | Path |
|----------|------|
| Index CSV | `cursor-bundle/reference/db/prod-indexes-baseline.csv` |
| Manifest | `cursor-bundle/reference/db/prod-indexes-manifest.json` |
| Memory | `cursor-bundle/memory/reference_prod_db_indexes_baseline.md` |

**Current snapshot:** 2026-06-19 production export (2432 rows).

## Workflow (two layers)

### Layer 1 — Prod baseline (always, no DB)

```bash
bash scripts/bin/query-index-perf-audit.sh --prod-lookup mfi_accounting.<table>
bash scripts/bin/query-index-perf-audit.sh --group <profile> --prod-baseline
```

| Prod baseline | Action |
|---------------|--------|
| `NOT_IN_PROD` | Include in Flyway + `scripts/sql/setup/` in **same improvement PR** |
| `IN_PROD` | Do not duplicate; align query to existing index columns |
| PK-only on hot batch table | Design composite indexes from **full query matrix**, not one query in isolation |

### Layer 2 — Live EXPLAIN (validate)

```bash
bash scripts/bin/query-index-perf-audit.sh --group <profile> --db qa4 --prod-baseline
```

Steps: grep predicates → Layer 1 → matrix JSON → design indexes → Layer 2 → row count × per-chunk multiplier → verdict.

## Index design rules (platform)

1. **Inventory all callers** on the table (batch readers, repositories, count queries) before creating indexes.
2. **Split indexes** when predicates conflict (point lookup by `dfc_id` vs partition scan by `inout_status + id`).
3. **Flyway + ops script** — same DDL in both; document in matrix JSON.
4. **Yugabyte LSM** — leading HASH columns match existing prod patterns; verify against baseline CSV.

## Verdict rules

| Verdict | When |
|---------|------|
| **PASS** | Index scan on live EXPLAIN, or improvement ships Flyway covering all matrix queries |
| **WARN** | Small QA table seq scan; Flyway included, not yet applied on QA |
| **FAIL** | Improvement PR without indexes when prod baseline is PK-only on hot path; high cost at scale |

## Profile groups

| Group | Table / flow |
|-------|----------------|
| `dcf_insurance_reupload` | Death foreclosure insurance staging RE_UPLOAD |

Add groups in `query_index_perf_audit.py` → `PROFILE_GROUPS` + matrix JSON alongside.

## Agent output (Improvement ship note)

```text
Mode: Improvement (best solution)
Cross-service deploy: <services — must list pairs>
Prod index baseline (2026-06-19): <NOT_IN_PROD: idx_... | IN_PROD: ...>
Query matrix: <N queries, M indexes>
Query index audit: PASS | WARN | FAIL
Poison-row guard: <predicate / status machine change>
Per-item query multiplier: <N DB round trips per batch row>
Hot-path scan: PASS | WARN
```

## Registry

- `dcf.insurance_reupload_index_audit` — after DFC insurance SQL changes

## Refresh prod baseline

User provides newer `prod-indexes-*.csv` → overwrite baseline CSV → update manifest → changelog kb-only row.

## Pair with

- `.cursor/rules/20-ship-gates.mdc`
- `.cursor/rules/10-quality-gates.mdc`
- `.cursor/skills/reuse-queries-java-filter/SKILL.md`
