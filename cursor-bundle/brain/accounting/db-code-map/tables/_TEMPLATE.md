# `mfi_accounting.<table_name>`

> One-line description: what this table represents in the LMS.

## Purpose

(One paragraph. Why does this table exist? What business concept does it model?)

## Schema (live from mfi_qa3)

Re-fetch any time with `tools/inspect-table.sh <table>`.

| Column | Type | Null? | Meaning / business intent |
|---|---|:-:|---|
| `id` | bigint | NOT NULL | PK |
| ... | ... | ... | ... |

### Key columns to know

- `<col>` — (why it matters)

### Indexes

(Listed by `inspect-table.sh`. Note any non-obvious ones, e.g. composite indexes used by hot queries.)

## JPA entity

[`<path>:<line>`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/...)

Notes:
- Inheritance? (e.g. `@PrimaryKeyJoinColumn` if JOINED-inheritance)
- Enums embedded? (e.g. `@Enumerated(EnumType.STRING)`)
- Listeners (`@EntityListeners`)?

## DAO + Repository

| Class | File |
|---|---|
| `<TableName>DAOService` | path |
| `<TableName>Repository` | path |

## Writers

Processors that **INSERT** or **UPDATE** this table:

| Processor | Action | Triggered by Request | Notes |
|---|---|---|---|
| `createXProcessor` | INSERT | `disburseLoan` (function_sub_code=DEFAULT) | sets initial loan_status=APPROVED |
| `updateXStatusProcessor` | UPDATE | `<request>` | flips loan_status |
| ... | ... | ... | ... |

## Readers

Processors that **SELECT** from this table:

| Processor | Triggered by Request | Purpose |
|---|---|---|
| `getXDetailsProcessor` | `getLoanAccountDetails` | API response |
| ... | ... | ... |

## Related Requests

Orchestration `<Request name="…">` entries that touch this table (writes or reads):

- `disburseLoan` (mfi_orc.xml:4) — writes
- `loanRepayment` (mfi_orc.xml:2661) — writes (status updates) + reads
- `getLoanAccountDetails` — reads
- ...

## Related flows

- [`../../flows/disbursement-end-to-end.md`](../../../flows/disbursement-end-to-end.md) — discusses this table as part of the disbursement state machine
- [`../../runbooks/disbursement-stuck.md`](../../../runbooks/disbursement-stuck.md) — first-SQL queries this table

## Common diagnostic queries

```sql
-- Lookup by a key field
SELECT * FROM mfi_accounting.<table> WHERE <key> = ? LIMIT 5;

-- Recent activity
SELECT * FROM mfi_accounting.<table>
 WHERE updated_on >= NOW() - INTERVAL '1 day'
 ORDER BY updated_on DESC LIMIT 20;
```

## Gotchas

- (Non-obvious behaviour. Concurrency issues. NULL semantics. Migration history. etc.)

## Sample row(s) from mfi_qa3 (anonymised)

(Optional — paste a representative row to ground the schema. Mask any PII first.)
