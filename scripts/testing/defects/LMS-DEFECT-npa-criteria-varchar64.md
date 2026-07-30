# LMS-DEFECT — NPA / AssetCriteria varchar(64) overflow (RECLASSIFIED)

**Date:** 2026-07-30 (reclassified same day)  
**Prior label:** URGENT NPA product varchar(64) at AssetCriteria postTransaction:300  
**Status:** RECLASSIFIED — not an AssetCriteria product STAN/client_ref construction bug

## Root cause (proven)

| Layer | Finding |
|-------|---------|
| **Primary (harness)** | `scripts/testing/lib/api_client.py` `batch_envelope` built `stan = fresh_stan(api)_{api}` → e.g. `loanAccountAssetCriteriaJob_<ms>_loanAccountAssetCriteriaJob` **len=69** while `transaction_master.stan` is **varchar(64)**. AssetCriteria uses `generateNewStan=false` and reuses caller STAN. |
| **Product gap (real, lower urgency)** | `postTransaction` Request had **no** `stringLengthValidator` on `stan` / `client_reference_number` → Hibernate SQLState 22001 wrapped as deep **333** / “Unexpected Error Occured” (silent skip after D1). |
| **Masking (D1)** | `GenericListenerV3.onSkipInWrite` CCE (`FutureTask`→`List`) failed the step before honest skip audit. |

## Not the root

- Do **not** change AssetCriteria product code to invent shorter STANs.
- `client_reference_number = accountNumber + millis` at BatchProcessor:296 is ≤64 for normal LANs.

## Fix direction

1. Harness: single-append STAN ≤64 (`api_client.py` / `envelope.py`).  
2. API: `product_transaction_orc.xml` `stringLengthValidator` maxLength=64 on `stan` + `client_reference_number` (mandatory **dropped** — see caller audit; 4 internal callers inherit EC).  
3. D1 already: unwrap Future in SkipListener + cause chain.

## Urgency (revised)

| Was | Now |
|-----|-----|
| URGENT NPA product defect | **Harness P0** (local/ship-test self-inflicted) + **Product P2** (missing length validators / opaque 333) |

## Residual after harness fix (exec 3877053)

1 skip: `Invalid amount` [132160] on `context_value=76460` — triage in companion note; not varchar/STAN.
