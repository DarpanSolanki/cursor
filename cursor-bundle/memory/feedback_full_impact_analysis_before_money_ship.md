# Full impact analysis before money ship (fail-closed)

**Standing (2026-07-19):** Money-tier ships must record an **impact matrix** in `.cursor/.ship-discipline.json` → `impact_analysis` before ship-loop / workspace-close. Soft essays were skipped; the gate now fails closed.

## Required keys (each ≥8 chars)

| Key | Meaning |
|-----|---------|
| `entry_paths` | Flow matrix: orch APIs, batch jobs, Kafka consumers (not only QA-cited path) |
| `scenario_modes` | last-child / non-last / standalone / replay — which in scope |
| `callers` | Orch beans / processors / queue populators; grep changed methods |
| `downstream` | Webapp APIs, GL legs, events, registry case ids |
| `modes` | Payment modes in/out of scope (e.g. CASH skip, DIRDR/ACH check) |
| `account_field` | Exact field compared (e.g. `repayment_account_number` vs mandate CASA) |
| `error_codes` | Fail codes + when each fires |
| `happy_path` | Why matching SHG/JLG still passes |
| `blast_radius` | Sibling processors, product vs MFI beans, CLB key threading |
| `out_of_scope` | Explicit Out-of-scope rows **with evidence** (why not touched) |

**Tiers:** money always; **service** on accounting/payments/LOS repos also requires the block.

## Write

```bash
bash scripts/bin/ship-discipline.sh write \
  --minimal-fix "…" --read-path No --hot-path PASS \
  --verify-mode PROCESSOR_MIRROR_SIM --kg CASES --assumptions-none \
  --impact-entry-paths "deathForeclosureInsuranceJob; loanDeathForeclosure" \
  --impact-scenario-modes "last-child; non-last; standalone Out-of-scope" \
  --impact-callers "customValidate… + ValidateDisbursement… + CLB populator" \
  --impact-downstream "getLoanAccountSummaryDetails; GL BILLING; registry dcf.*" \
  --impact-modes "CASH skip; DIRDR/ACH match" \
  --impact-account-field "repayment_account_number vs rad.account_number" \
  --impact-error-codes "134382 no mandate; 134348 mismatch/missing CASA" \
  --impact-happy-path "SHG group CASA inherit matches group mandate" \
  --impact-blast-radius "createOrUpdateLoanAccount; childLoanDisbursement; CLMT customValidate" \
  --impact-out-of-scope "replay idempotency — evidence: writer client_ref no-op only"
```

## Why

Without this, agents ship money-path validators with incomplete caller/mode analysis (mandate match class). Pair with `10-quality-gates.mdc` + `20-ship-gates.mdc`.
