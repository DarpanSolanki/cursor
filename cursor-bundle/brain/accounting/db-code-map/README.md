# LMS database ↔ code cross-reference

> Goal: for every table in `mfi_accounting`, document which APIs/Requests/processors **write** to it, which **read** from it, what each non-obvious column means, and which flows touch it.
>
> Source of truth — combined:
> - **Live schema** from `mfi_qa3` (via `db-tools`). 179 tables, ~1700 columns total.
> - **Code** under `/home/darpan/darpan/novopay-platform-accounting-v2/` (entities, DAOs, processors, orchestration XMLs).

## Status

This is **incremental coverage**. As of last edit:

| Coverage tier | Tables | Status |
|---|---|---|
| **Tier 1 — Core LMS** (loan account, transaction, GL, accrual, asset criteria) | ~20 | Documented in `tables/` |
| **Tier 2 — Servicing** (foreclosure, prepayment, restructuring, reopening, NOC, insurance) | ~30 | On the roadmap; use `tools/inspect-table.sh <name>` for live data |
| **Tier 3 — Disbursement mechanics + mandates** (eNACH, SI, bank-call retry) | ~30 | On the roadmap |
| **Tier 4 — Bulk staging + tax + product masters** | ~50 | On the roadmap |
| **Tier 5 — Misc** (audit, file_staging_*, dump tables) | ~50 | Lowest priority |

## How this folder is structured

```
db-code-map/
├── README.md                 ← this file
├── 00-INDEX.md               full table list with coverage status
├── tables/                   one .md per table (tier 1 documented; others stubs/empty)
│   ├── _TEMPLATE.md          structure for any new table doc
│   ├── loan_account.md       Tier 1 ✅
│   ├── loan_due_details.md   Tier 1 ✅
│   ├── ...
├── by-flow/                  flow → tables touched
│   ├── disbursement.md
│   ├── repayment.md
│   ├── eod-bod.md
│   ├── shg-jlg-fanout.md
│   ├── npa-classification.md
│   └── foreclosure.md
├── by-request/               (future) Request → tables it writes/reads
└── tools/
    ├── inspect-table.sh      generate a live snapshot of any table
    └── (future) build-coverage-report.sh
```

## How to use this

### Quickest answer for any table

```bash
/home/darpan/darpan/claude/accounting/db-code-map/tools/inspect-table.sh <table_name>
```

Dumps live schema + indexes + row count + JPA entity location + DAO/repository neighbours + processors that import it + orchestration Requests wiring those processors. Works on any of the 179 tables.

### When you want curated knowledge

Open the matching doc under `tables/`. Each doc has the same structure:

```
# <table_name>

## Purpose            (one paragraph)
## Schema             (column-by-column with meaning, defaults, key indices)
## JPA entity         (file:line)
## DAO + repository   (file paths)
## Writers            (processors that INSERT/UPDATE this table, with Request context)
## Readers            (processors that SELECT, with Request context)
## Related Requests   (orchestration Requests that touch this table)
## Related flows      (links into ../../flows/ docs)
## Common queries     (canned diagnostic SQL)
## Gotchas            (non-obvious behaviour)
```

### When you want to trace a flow

Open the matching doc under `by-flow/`. Each lists the tables it writes/reads in execution order, with code anchors.

## Methodology used to author the curated docs

For each Tier 1 table:

1. Run `tools/inspect-table.sh <table>` to get live schema + entity/processor candidates.
2. Open the JPA entity to map column-comments / annotations to business meaning.
3. Open every processor that imports the entity; for each:
   - Identify if it reads or writes
   - Find the orchestration Request(s) that wire it (`grep "bean=\"<beanName>\"" deploy/.../orchestration/*.xml`)
   - Note the EC keys that flow in/out
4. Cross-reference against existing flow docs (`../../flows/*`).
5. Run a few real-data queries from `mfi_qa3` to validate column semantics.

## Boundary

- Live schema reads via `db-tools/bin/db-query.sh mfi_qa3` (tier=qa, read-only, no creds in this folder).
- Code reads from `/home/darpan/darpan/novopay-platform-accounting-v2/` only.
- Nothing writes outside `/home/darpan/darpan/`.

## Contributing

When you discover a new fact about a table or column, edit the table's `.md` directly. Keep `file:line` citations current — they go stale fast.

When adding a new table doc:
1. Copy `tables/_TEMPLATE.md` to `tables/<table>.md`
2. Run `inspect-table.sh <table>` and paste relevant outputs
3. Walk the methodology above
4. Update `00-INDEX.md` to mark this table covered
5. If the table is touched by an existing flow doc, link it there

## Cross-references

- LMS data-model overview (table clusters): [`../09-data-model.md`](../09-data-model.md)
- Posting engine internals: [`../08-gl-posting-engine.md`](../08-gl-posting-engine.md)
- SHG/JLG model: [`../06-shg-jlg-group-loans.md`](../06-shg-jlg-group-loans.md)
- All accounting deep-dive: [`../INDEX.md`](../INDEX.md)
