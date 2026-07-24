# Child GL codes are CG* — never rename to parent GL names

**Date:** 2026-07-24 · **Ticket:** TDPQA-72 · **Train:** accounting `mfi_integration_v3.4.2.4`

## Mistake

Handoff / report showed child force-bill settlement as parent-style names (`REG EMI-JLGDL- BI` / `INT ACC NOT DUE-JLGDL-AIR`) by stripping `CG` and joining `general_ledger.name`. Stored child `tpd.gl_code` is **`CG13336` / `CG13578`** (`is_child_gl_code=true`). Parent stores bare **`13336` / `13578`** with those names.

## Code SoT

- Prefix: `ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX = "CG"`
- Apply: `ExecuteTransactionRulesProcessor` when `is_child_account=true` → `gl_code = "CG" + glAccountId` (also sets `is_child_gl_code`)
- Brain already had this in `accounting/08-gl-posting-engine.md` + `flows/shg-jlg-group-loan.md` — **agents still invented display names** because harness/registry only asserted debit==credit.

## Hard rules for agents

1. Quote **`transaction_partition_details.gl_code` as stored** — do not strip `CG` for child legs in JIRA/reports.
2. Parent named GL (`general_ledger.name`) is OK **only** when `gl_code` has no `CG` prefix / `is_child_gl_code=false`.
3. `ia_code` / `account_number` on the partition may still be the bare numeric code even on child rows — that is **not** the display GL code.
4. Harness: `assert_force_bill_gl_shape` prints/verifies CG vs named on force-bill BILLING refs.

## Why workspace “missed” it

| Layer | Had CG? | Gap |
|-------|---------|-----|
| Brain GL engine + SHG flow | Yes | Not wired into force-bill acceptance / JIRA proof templates |
| Memory / TDPQA-72 feedback | No until this file | No standing “never rename CG” correction |
| Registry `db_asserts` | debit==credit only | No shape assert on `gl_code` prefix |
| `assert_gl_balanced_txn` | Balance only | Soft **Out-of-scope** when 0 partitions — skips proof |
| KG FTS | Internal-account APIs | No force-bill display convention node |

## Blockers to fuller platform knowledge

- Provisional / mixed-train KG watermark → agents treat flow docs as optional under HARD STOP ACK
- Enrichment incomplete for display conventions (code→brain exists; brain→harness/registry/JIRA templates do not)
- Soft Out-of-scope on missing local partitions hides GL shape failures
- Join heuristics (strip CG → parent name) look “helpful” and bypass SoT
