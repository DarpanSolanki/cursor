<!-- VERBATIM archive of former alwaysApply `.cursor/rules/ship-test-mandatory.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Ship test mandatory (all fixes — not only DPI/money)

**Rule:** Any change under a service repo (`novopay-*`, `trustt-*`), workspace scripts, or orchestration must be **verified locally** before push or JIRA "ready for QA".

## Agent workflow (non-negotiable)

```
edit → compile (if Java) → workspace-close.sh --from-pending → then push / release details
```

Do **not** push after `compileJava` alone. HTTP 200 on a batch trigger is **not** enough — batch cases wait for `COMPLETED`.

## What enforces this

| Layer | Behaviour |
|-------|-----------|
| **post-commit hook** | Registers `.cursor/.pending-ship-work.json` from committed ship paths |
| **pre-push hook** | Auto `workspace-close` or **deny** until `ship_push_gate --satisfied` |
| **push-origin.sh** | Same gate; never bypass with raw `git push` |
| **ship-loop tiers** | workspace: validate + smoke · service: build + health/ntest · money: build + flow ntest |

## Minimum test by tier

- **workspace** — `kg validate` + `ntest validate` (+ flow-scoped case if resolved)
- **service** — `gradlew build -x test` + health probe or `ntest smoke --quick`
- **money** — build + registry case (`batch.*` preferred over certify flows) + batch `COMPLETED` when applicable + **value-level DB asserts** (below)

## Real-flow DB write validation (money ships — mandatory, fail-closed)

`feedback_real_flow_db_write_validate.md`. A money ship is **not** verified until the REAL flow ran and every touched table's **column values** were read back and matched to expected — not presence, not SQL-only "should have inserted", not a status-200/COMPLETED alone.

- Drive the actual orchestration / API / job / batch a production transaction takes (e.g. `deathForeclosureInsuranceJob`, `loanRepayment`, disburse) — never a hand-written INSERT to fake the row.
- After each critical write, assert exact values: `loan_account_billing_details` (EMI preserved + dedicated FB interest/prin/txn_ref/installment_id), `transaction_master` client_ref + original_amount, `loan_account_payments_details` amount/principal/excess/interest, `interest_accrual_details` accrued vs billed, `is_deleted`/reversed flags.
- **Machine gate:** enforced money domains must declare `acceptance.db_asserts` (or registry `expect.db_eq`) covering every `domain_money_tables` entry (`scripts/lib/acceptance_coverage_manifest.json`); each entry needs `table` + `expect|assert|columns` + `checked_by` evidence. Presence-only phrasing is rejected. Enforced via `acceptance_coverage.py` inside `ship_discipline_gate` / `ship-loop-gate`. **CRR / `client_request_response_log` (incl. inbound callback):** money-tier disbursement requires column contracts including `client_reference_number` even when the domain is still dimension-backlog — `PROCESSOR_MIRROR_SIM` without those columns fails closed (`feedback_crr_callback_column_assert.md`).

## Adversarial fixture matrix (money ships — mandatory)

A green happy-path e2e is **not** proof. Money ships must cover each row, or **document Out-of-scope** with a reason (`feedback_qa_acceptance_not_subset_verify.md`):

| Path | Why |
|---|---|
| **happy path** | baseline |
| **dirty / pre-existing state** | QA runs on production rows, not clean seeds (e.g. pre-existing EMI labd on the death-cycle installment — `DCF_SEED_EMI_LABD=1`) |
| **UI / component equality** | statement `amount == principal`/component; a delta is allowed **only** if the legs are documented and the assert checks them |
| **Webapp-bound APIs** | If the fix changes amounts, labd/billing, Accrued/Original, DFC/foreclosure, or payment components: live `getLoanAccountSummaryDetails` / `getLoanAccountOverviewDetails` (`account_number_list`) / `getLoanAccountStatement` — SQL-only is **not** webapp verified (`feedback_webapp_verify_mandatory_ui_ships.md`) |

**The assert must FAIL on the exact QA fail mode** — never print "OK …"/"WARN …" and pass. Debug relax flags (`ACCEPTANCE_STRICT=0`) never yield a handoff Pass.

## When full flow E2E cannot run

Do **not** skip the ship gate. Follow `.cursor/rules/code-backed-simulation-testing.mdc`:

1. Prefer realtime / staged ntest.
2. If a stage is blocked → add/run a **code-backed** registry sim (`verify_mode: orch_sibling_sim` / `processor_mirror_sim`) that parses real orch XML / Java — never guessed expects.
3. Label claims `ORCH_SIBLING_SIM` (etc.); enrich the platform suite in the same change.

## After test PASS

Before money/service `workspace-close` / ship-loop PASS, write discipline (fail closed):

```bash
bash scripts/bin/ship-discipline.sh write \
  --minimal-fix "<one permanent-fix sentence>" \
  --read-path No \
  --hot-path PASS \
  --verify-mode RUNTIME_VERIFIED \
  --kg CASES \
  --assumptions-none
```

Then `workspace-autopilot.sh mark-verified` or full `workspace-close`. Prefer `bash scripts/bin/push-origin.sh --repo <service>`.

## Escape hatch (rare)

`SHIP_PUSH_NO_AUTO_CLOSE=1` — push denied until manual `workspace-close`; use only when debugging the gate itself.
