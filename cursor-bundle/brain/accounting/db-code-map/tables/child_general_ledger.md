# `mfi_accounting.child_general_ledger`

> Parallel chart of accounts for SHG/JLG **child loan** transactions. Codes are prefixed with `CG` and mirror the parent GL chart.

## Purpose

When a SHG/JLG child loan posts a transaction, the engine prefixes the GL code with `CG`. The child GL is a separate row from the parent GL but mirrors its name/category/balance type. This keeps parent and child posting streams cleanly separable in trial balance and reporting.

## Schema (live, 18 cols)

Mirrors `general_ledger` plus:

| Column | Meaning |
|---|---|
| `parent_gl_id` | FK → `general_ledger.id` (the GL this child mirrors) |
| `code` | The CG-prefixed code (e.g. `CG230101`) |
| All other columns | Same as `general_ledger` |

## JPA entity

[`generalledger/entity/ChildGeneralLedgerEntity.java`](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/generalledger/entity/ChildGeneralLedgerEntity.java) — defines `CHILD_GL_CODE_PREFIX = "CG"` and a static `mapToChild(GeneralLedgerEntity)` factory.

## Writers

- `mapToChild()` factory used during disbursement / GL CRUD when child GL needs to be auto-created
- Child-GL admin Requests (parallel to GeneralLedger ones)

## Readers

- [`ExecuteTransactionRulesProcessor.createPartitionDetails` lines 391-393](../../../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L391-L393) — when `is_child_account=true` in EC, prepends `CG` to `gl_code` on every leg
- TB calculation reads it for child-side aggregation

## Related Requests

- All `child*` Requests in `group_mfi_orc.xml` that hit `<API id="postTransaction">`

## Related flows

- [SHG/JLG group loan](../../../flows/shg-jlg-group-loan.md)
- [GL posting engine §3 phase 2](../../08-gl-posting-engine.md#3-executetransactionrulesprocessor--the-engine-itself)

## Common queries

```sql
-- Child-GL distribution
SELECT category, COUNT(*) FROM mfi_accounting.child_general_ledger
 WHERE is_deleted=false GROUP BY 1;

-- Find a child GL for a given parent code
SELECT cgl.code AS child_code, gl.code AS parent_code, gl.name
  FROM mfi_accounting.child_general_ledger cgl
  JOIN mfi_accounting.general_ledger gl ON gl.id = cgl.parent_gl_id
 WHERE gl.code = ?;
```

## Gotchas

1. **`CG` prefix is hard-coded** in `ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX`. Don't confuse with other prefixes.
2. **Routing depends on `is_child_account` EC flag** — caller must set this in `populateAdditionalInformationProcessor` IParams.
3. **Forgetting to set `is_child_account=true`** = child txn posts to parent GL → trial balance asymmetry on parent GL.
