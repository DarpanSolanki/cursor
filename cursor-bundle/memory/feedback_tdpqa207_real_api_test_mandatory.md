# Feedback: never skip real API test after money fix

**When:** 2026-07-29  
**Trigger:** TDPQA-207 — agent compiled + pushed fix branch after `compileJava` only; no real `getLoanForeclosureDetails` BY_LATEST call. Push to train later blocked by workspace-close (correct), but origin fix-branch push had already gone out without ntest.

## Root causes

1. **Agent behaviour** — treated compile-green as enough; skipped `impact-tests` / `ntest` / restart-with-fix.
2. **Wrong change→api map** — `PrepaymentDetailsRepository` matched `/loan/prepayment/` → `loanPrepayment`, so impact plan never selected `getLoanForeclosureDetails` / BY_LATEST case.
3. **Missing registry case** — no `foreclosure.by_latest_details_api` asserting REJECTED must not win on future business `created_on`.

## Permanent contract (2026-07-29)

1. Map: `GetLoanForeclosureDetailsProcessor` + `PrepaymentDetailsRepository` → `getLoanForeclosureDetails` (before `/loan/prepayment/` → `loanPrepayment`).
2. Registry: `foreclosure.by_latest_details_api` (runtime flow; seeds future REJECT* `created_on`; asserts BY_LATEST ≠ REJECTED/REJECT). Domain `foreclosure` impact/release includes it.
3. ntest: registry may set `function_sub_code` / `headers` overrides via `build_envelope(header_overrides=…)`.
4. **Do not** `git push` accounting money after `compileJava` alone — run `ntest run foreclosure.by_latest_details_api` (or `workspace-close --from-pending`) with service restarted on the fix branch.

## Agent rule

Money-path fix DoD = **real API (or blocked+sim ladder)** this session + impact `--mark-ran`. Compile ≠ tested.
