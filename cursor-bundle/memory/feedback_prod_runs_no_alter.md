---
name: prod-runs-no-alter
description: The manual Flyway pack is for ALTER/DDL only — INSERT/UPDATE migrations run normally and need no pack
metadata:
  type: feedback
---

The manual Flyway deploy pack is required for **ALTER/DDL only**. INSERT/UPDATE migrations run
through Flyway normally in production and need no pack, no `flyway_schema_history` row written by
hand, and no separate DBA conversation.

**Why:** corrected by Darpan twice (2026-08-05, 2026-08-06) on TDPQA-241. The first version of this
memory said "schema releases ship INSERTs plus a flyway_schema_history row", which wrongly dragged
pure-DML migrations into the manual path and inflated the cost of every fix that only adds rows.

**How to apply:**

| Migration content | Production path |
|-------------------|-----------------|
| `INSERT` / `UPDATE` only — error codes, notification messages, master data, config rows | Runs normally. **No pack.** Ship the migration and stop. |
| `ALTER` / `CREATE` / any DDL | Manual pack: DDL + `flyway_schema_history` INSERT + pre/post timing, via `flyway-prod-deploy-pack.sh` |

So when weighing options: a fix expressible as new rows is cheap to deploy — do not price it as a
schema release. A fix needing a new column or table carries the manual-DDL cost; say that explicitly
and treat it as its own release conversation.

Worked example: `V9000429__add_msg_for_disbursement_in_progress_update.sql` (TDPQA-241) is two
INSERTs into `notification_message` and `code__notification_code__mapping` — no pack, in QA or prod.

Pairs with [[reference-forward-merge-chain]] for allocating migration versions against the highest
chain branch.
