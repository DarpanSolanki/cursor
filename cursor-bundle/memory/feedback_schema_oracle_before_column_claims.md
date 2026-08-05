# Resolve every column against the oracle before naming it

**Trigger:** 2026-08-05. Darpan: *"many a time I have seen you are referring to columns in table
which do not exist."* He was right, and it was measurable.

## The evidence

- `loan_account_payments_details.is_deleted` sat in **two money-tier registry asserts**
  (`dpic.repayment_e2e`, `foreclosure.individual_child`). That table is append-only and has no
  soft-delete column. The token was copied from the `loan_due_details` context in
  `scripts/dpic/sql/helpers/verify_dpi_repayment.sql`, where `is_deleted` is real.
- Of 60 `loan_product` business columns, **47 appeared nowhere** in the 1.97 MB knowledge corpus —
  including `prepayment_allowed`, the column Darpan named as the example.
- Only **14 `expect` keys existed across all 178 registry cases**. The value-level assert layer is
  far thinner than the rules imply.

## The rule

**Never write a column name into an assert, a doc, a SQL file or a sentence without resolving it.**

```bash
python3 cursor-bundle/kg/bin/kg.py schema loan_product.prepayment_allowed
```

That returns structure (type, nullability, default, PK), the JPA entity field, the readers/writers,
the native-query repositories, the **error code the readers throw**, and a train label. For a config
column the readers *are* the semantics: `prepayment_allowed` false → `ValidateLoanPrepaymentProductProcessor`
throws **134144**. Refresh with `bash scripts/bin/schema-sync.sh`.

`scripts/lib/schema_ref_gate.py` now fails the ship gate on any unresolvable reference, so this is
enforced rather than remembered.

## Coverage (2026-08-05)

All 14 schema-owning services are mapped: 744/845 tables carry an entity, 13,444 columns mapped,
10,748 code-bound. `column_binding.py --coverage` prints the per-service table.

## A repo does not imply a schema (2026-08-05)

`trustt-platform-lib` was skipped entirely because it owns no schema — 2346 Java files across 32
subprojects, unmapped. Two structural lessons that are not lib-specific:

- **Resolve each entity's table against the oracle, never from its repo.** `hierarchy-builder` in
  lib writes `mfi_actor`; `sequences` exists in 17 schemas. `column_binding.resolve_schema()`.
- **Composite builds have no `repo/src/main/java`.** Sources live in `*/src/main/java`. Any scanner
  that assumes the single-module layout silently returns zero for lib — that is how its tables were
  missing from the KG.
- **`novopay-platform-lib` is a SYMLINK to `trustt-platform-lib`.** Follow it and every lib table is
  owned twice, with the alias winning the name because it sorts first. Skip a symlinked repo when
  its target is also being scanned.
- **`@Table(name="\"user\"")`** maps a reserved word as a quoted identifier — unescape before use,
  or the table is recorded as `\`.

## Three accuracy traps the extension exposed

- **Bare table names are ambiguous.** 18 names live in >1 schema, 6 with different columns
  (`client_request_response_log` in accounting/audit/los). Always resolve `(schema, table)`;
  qualify as `mfi_los.client_request_response_log` to target a sibling.
- **Field names collide across entities.** 73% of columns share a field name with another entity
  in the same service, so keying readers by name alone attributed nine unrelated error codes to
  `status`. Callers are receiver-matched; ambiguous columns are labelled and favour precision over
  recall.
- **Never share an accessor index across repos.** `getAmount()` exists in several services.

## Two traps found while building it

1. **Mis-attribution beats invention.** The wrong columns were all *real columns of other tables*.
   Checking "does this string look like a column?" finds nothing; checking "is it a column of
   **this** table?" finds everything. Prose shorthand (`debit`, `pending`, `prin_pending`) exists on
   no table at all and must not be flagged, or the gate becomes noise and gets disabled.
2. **The local DB is not product truth.** It carries hand-applied fixture patches — 196
   `mfi_accounting` columns match no migration, `loan_account.dpi_suspense_amount` (GAP-076) among
   them. `train-diff.json` labels these; never build a cross-train contract on a local-only column.

Related: [[feedback_gates_must_be_provably_failable]], [[feedback_suite_workarounds_hide_the_defect]],
[[feedback_yugabyte_id_order_is_not_recency]].
