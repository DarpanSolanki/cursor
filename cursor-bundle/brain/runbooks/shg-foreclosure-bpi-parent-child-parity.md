# SHG parent foreclosure BPI ≠ sum(children) — SDCP-11058

> **Domain:** `foreclosure` (not death_foreclosure). Train: `mfi_integration_v3.4.2.1`.
> **Symptom:** Parent BPI (e.g. 79) ≠ sum of child BPI legs (e.g. 39+39=78) after SHG/JLG parent foreclosure. Works for **any N≥1** children (not only 2×0.5).

## First check

```sql
-- scripts/sql/helpers/verify_shg_foreclosure_bpi_parity.sql
\set parent_lan '''6009717926'''
\i scripts/sql/helpers/verify_shg_foreclosure_bpi_parity.sql
```

## Root cause

`ChildLoanForeclosureProcessor` used each child’s independent sim `bpi_amount` (HALF_UP per loan). Fees already used `groupLoanUtility.getDistributedAmountEqually(parentDue, childLoanBookingDTOList)` so sum(fees)=parent. BPI did not → classic round-twice drift.

## Fix (L1)

Same branch as `foreclosure_fee`: distribute **parent** BPI across the full `childLoanBookingDTOList` (any N; residue on last child). Source of truth = parent quote.

## Verify

- Unit: `ntest run foreclosure.shg_bpi_parity` (N=1..20 distribute mirror)
- Full FC: omit `UNIT_ONLY`; optional `SHG_BPI_MEMBER_COUNT=3` / `PARENT_LAN=` for N≠2

## Related

- SDCP-11012 — same class for **DPI** accrual (adjust service); different path
- Runbook index · JIRA SDCP-11058
