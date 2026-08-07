# Never guess a column — the query path checks for you now

Darpan, 2026-08-07: *"workspace does not know which columns are there and which are not…
when creating any select query, workspace should know what columns exist in the database
and schemas — do not assume anything."*

## Two different failures, two different tools

| Symptom | Meaning | Tool |
|---------|---------|------|
| `column "x" does not exist` from psql | the column was **guessed** | `sql_column_check.py` (auto, in `db-local.sh`) |
| `Unable to find column position by name: x` at runtime | the code maps it, the **local DB is behind** | `python3 scripts/lib/schema_live_drift.py` |

```bash
python3 cursor-bundle/kg/bin/kg.py schema <table>     # what columns actually exist
python3 scripts/lib/schema_live_drift.py --schema mfi_los
bash scripts/bin/schema-sync.sh                        # refresh after migration / branch switch
```

## What is automatic

`scripts/db-local.sh` runs `sql_column_check.py` **before** psql. A confident miss is
refused, naming the table and offering near-matches, with no round trip. It deliberately
stays silent on CTEs, subquery aliases and unknown tables — a checker with false positives
gets switched off, and then it protects nothing. Escape: `DB_LOCAL_SKIP_COLUMN_CHECK=1`.

It catches the real historical traps: `loan_account_payments_details.is_deleted` (no such
column on an append-only table — it shipped in a money-tier assert) and typos in `WHERE`,
which are worse than errors because the query just returns nothing and the RCA goes wrong.

## The trap that cost an hour

`mfi_los.loan_app.vrm_category`: `LoanAppEntity` mapped it, `V000001__table.sql` declared
it, the **local DB predated it**. `getTaskDataFromLos` failed and it read as a code bug.
The oracle is built from the **live DB**, so "column absent" can mean the DB is behind —
not that the column does not exist. Fix by applying the migration or ALTERing the local
table to the migration's type. **Never invent a type.**

Related: [[reference_java_probe_harness]]
