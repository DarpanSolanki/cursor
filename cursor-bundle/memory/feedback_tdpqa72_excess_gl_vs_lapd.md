---
name: feedback_tdpqa72_excess_gl_vs_lapd
description: Restore Sheet15 EXCESS_* on child+parent RSCH; keep lapd.excess=0 for UI Obs ₹54
---

# TDPQA-72 — EXCESS GL vs statement Excess

## JIRA 390372 Obs3 (Darpan action)

> ₹54 displayed in Excess component though already adjusted to Principal.

**Darpan fix (`9b6454df6`, 2026-07-22):** parent RSCH `EXCESS_*=0` **and** `lapd.excess_amount=0`.

UI Excess comes from **payment/LAPD** excess — keep **`lapd.excess=0`**.

## Vikram 391188 GROSS RCV (child-only EXCESS)

Zeroing **only parent** GL EXCESS while child still posted EXCESS → GROSS Δ (e.g. 52).  
`5f4661b03` then zeroed SHG child EXCESS too (compensating).

## L1 (2026-07-24, Darpan ask)

- Restore **GL** `EXCESS_*` on child DEATH **and** parent last-child RSCH (same Sheet15).
- Keep **`lapd.excess=0`** (390372).
- Do not reintroduce Accrued/IAD hacks.
