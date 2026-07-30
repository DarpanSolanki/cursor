# LMS-DEFECT #4 — AssetCriteria skip Invalid amount (132160)

**Date:** 2026-07-30  
**Evidence job:** `loanAccountAssetCriteriaJob` exec **3877053** (post D1 CCE unmask + harness STAN≤64)  
**context_value:** account_id **76460** / LAN **6000000262**

## Symptom

Write skip (honest audit after D1):
`NovopayFatalException: Invalid amount [errorCode=132160]`
at `LoanAccountAssetCriteriaItemWriter.write:84` → `postTransaction` → `ValidateTransactionDataProcessor.validateAmount`.

## Classification

| Layer | Verdict |
|-------|---------|
| Harness | **No** — STAN length skips gone on this exec; residual is amount validation |
| Env/data | **Poison local LAN** — INT dues: paid (1245) > due (1204) → net **-41**; PRIN waived sum exceeds due |
| Product | **Yes (edge)** — forward NPA amount builder can post `TOTAL_AMOUNT` that is **negative** or fails currency scale → 132160. Batch continues with skip (not step-fail). |

## Code path

`ValidateTransactionDataProcessor.validateAmount` (lines 71–83): amount `< 0` **or** `amount != currencyUtil.roundAmount(...)` → **132160**.

AssetCriteria: `populateForwardMovementAmountDetails` / reverse → `TOTAL_AMOUNT` → `postTransaction`.

## Urgency

**P3 / data+edge** — not the varchar(64) defect; not blocking NPA criteria for healthy LANs. Do **not** conflate with harness STAN double-append.

## Next (not this ship)

- Reproduce amount string for 76460 under forward movement (suspense + AIR).  
- Product: skip posting when total ≤ 0 (write-path guard) **or** ops clean poison dues.  
- Out of scope for D2 length-validator + harness commit.
