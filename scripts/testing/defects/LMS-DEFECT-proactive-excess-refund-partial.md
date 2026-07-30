# LMS-DEFECT / known — proactive excess refund no money move (PARTIAL)

**Date:** 2026-07-31 (bone-close)  
**Class:** PRODUCT / high-risk writer (not harness assert; not af52abe3d catch-up)  
**Case:** `flowtest.proactive_excess_refund` → PARTIAL  
**Evidence:** `scripts/scratch/bone/suite15/10-flowtest_proactive_excess_refund.log`

## Symptom
Staging + `proactiveExcessAmountRefund` COMPLETED; `excess_amount` unchanged (250.000000); no refund txn.

## Trace
Log: `PARTIAL: excess unchanged … SU-FLOW-EXCESS-RAILS / writer swallow / reader miss`  
Gaps digest High: `ProactiveExcessAmountRefundItemWriter` swallows exceptions (L156–L158).

## Decision (bone-close)
STOP — no product edit this round. Leave PARTIAL / known_defect path. Not fixture catch-up from booking fix.
