---
name: feedback_ship_loop_fc_touch_harness_blast
description: >-
  scripts/testing/foreclosure/* and loan/prepayment read DAO must not set
  fc_touch / force-full FC+DCF suite on push-origin. TDPQA-207 2026-07-29.
---

# Ship-loop over-select — BY_LATEST harness ≠ full FC money suite

## Failure (TDPQA-207 push)

`push-origin` from accounting ran `workspace-close` → ship-loop with **~1h17m / 10 full cases**
including `dcf.vikram_*`, `foreclosure.individual_child`, `flowtest.loan_prepayment_fc`.

Cause:
1. Pending included `scripts/testing/foreclosure/by-latest-details-api.sh`.
2. `_foreclosure_path_touch` matched substring `foreclos` (and formerly `loanprepayment`).
3. `_apply_selection_tiering` force-promoted every `foreclosure.*` / `dcf.*` domain case to **full**.
4. Foreclosure domain `impact_cases` + money `deep_cases` were always added for `getLoanForeclosureDetails`.

## Permanent fix

1. `_foreclosure_path_touch` — product **write** paths only; ignore `scripts/testing/`, `scripts/lib/`, knowledge.
2. Selection tiering — **domain_added** stays smoke unless api ∈ direct_apis; no harness→full escalation.
3. Domain JSON — `read_apis` + `read_impact_cases` for foreclosure; skip write/deep when read-only.
4. `push-origin` — set `SHIP_CLOSE_REPO` from service checkout so close scopes pending to that repo.

Expected BY_LATEST ship plan: `foreclosure.by_latest_details_api` + `dpic.foreclosure_details_api` + invariants/read_smoke (~minutes, not hour+).

## Agent rule

Do not treat “pending has money” as “run every domain impact_case”. Re-resolve with scoped paths; prove wall_planned_s before launching ship-loop.
