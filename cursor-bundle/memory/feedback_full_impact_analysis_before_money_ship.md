# Full impact analysis before money ship (fail-closed)

**Standing (2026-07-19):** Money-tier ships must record an **impact matrix** in `.cursor/.ship-discipline.json` → `impact_analysis` before ship-loop / workspace-close. Soft essays were skipped; the gate now fails closed.

## Required keys (each ≥8 chars)

| Key | Meaning |
|-----|---------|
| `callers` | Orch beans / processors / queue populators that hit the changed path |
| `modes` | Which payment modes are in / out of scope (e.g. CASH skip, DIRDR/ACH check) |
| `account_field` | Exact field compared (e.g. `repayment_account_number` vs mandate CASA) |
| `error_codes` | Fail codes + when each fires |
| `happy_path` | Why matching SHG/JLG still passes |
| `blast_radius` | Sibling processors, product vs MFI beans, CLB key threading |

## Write

```bash
bash scripts/bin/ship-discipline.sh write \
  --minimal-fix "…" --read-path No --hot-path PASS \
  --verify-mode PROCESSOR_MIRROR_SIM --kg CASES --assumptions-none \
  --impact-callers "customValidate… + ValidateDisbursement… + CLB populator" \
  --impact-modes "CASH skip; DIRDR/ACH match" \
  --impact-account-field "repayment_account_number vs rad.account_number" \
  --impact-error-codes "134382 no mandate; 134348 mismatch/missing CASA" \
  --impact-happy-path "SHG group CASA inherit matches group mandate" \
  --impact-blast-radius "createOrUpdateLoanAccount; childLoanDisbursement; CLMT customValidate"
```

## Why

Without this, agents ship money-path validators with incomplete caller/mode analysis (mandate match class). Pair with `minimal-fix-impact-gate.mdc` + `enhancement-all-fronts-gate.mdc`.
