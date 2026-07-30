# LMS-DEFECT — proactive excess refund COMPLETED with no money move (PARTIAL)

**Status:** known / STOP — no product FIX-PLAN this round  
**Class:** PRODUCT (writer swallows exceptions) — not harness assert, not af52abe3d  
**Case:** `flowtest.proactive_excess_refund` → honest **PARTIAL** (rc=0)  
**Evidence:** `scripts/scratch/bone/suite15/10-*.log`, `scripts/scratch/bone-close/suite15/10-*.log`

## Symptom (QA-visible)
1. Seed `loan_account.excess_amount=250` on LAN `6000137440`.
2. Fire `proactiveExcessAmountRefundStaging` + `proactiveExcessAmountRefund` → both **COMPLETED**.
3. `excess_amount` still **250**; no refund / excess-clearing txn.

Harness prints PARTIAL and still runs invariants — **does not claim Pass**.

## Writer + swallowed path (file:line)
`trustt-platform-accounting/.../proactiveexcessamountrefund/ProactiveExcessAmountRefundItemWriter.java`

| Lines | Behavior |
|------:|----------|
| 103–108 | `populateNarration` catch Exception → `narrationFailed=true` → **return** (no refund) |
| 115–118 | `callBankAPIForExcessAmountRefundProcessor.execute` catch Exception → `bankCallFailed=true` (empty catch body) |
| 126–129 | bank FAIL / `bank_api_status=FAIL` → `handleBankAPIFailResponse` + return |
| 156–158 | outer catch on success path: `LOG.debug("error in excess amount writer…")` only — **swallows**, staging may look done |

Gaps digest High row cites L156–L158.

## Repro
```bash
bash scripts/bin/ntest.sh run flowtest.proactive_excess_refund
# expect: === PARTIAL: flowtest.proactive_excess_refund ===
# assert today: jobs COMPLETED + excess unchanged (provable); NOT money-moved Pass
```

## Impact
Excess rails can report batch success while customer excess balance unchanged → ops/refund miss; silent bank/narration failures.

## Assert policy
Keep PARTIAL honest. Do **not** loosen to PASS when excess unchanged. Do **not** drop staging COMPLETED check.
