---
name: feedback_webapp_verify_mandatory_ui_ships
description: Money/UI-impacting ships must assert webapp-bound APIs (summary/overview/statement) — not SQL-only or overview-partial
---

# Webapp verify mandatory on UI-impacting ships

Triggered 2026-07-17 (TDPQA-72 / Darpan): fixes that change amounts, labd/billing, txn history,
summary Accrued/Original, DFC/foreclosure, or payment components **must** verify the APIs the
webapp calls — fail-closed.

## Required when UI impacted

| Screen / field | API | Assert |
|----------------|-----|--------|
| Summary Accrued / Original | `getLoanAccountSummaryDetails` → `interest_details.*` | Accrued ≤ Original (+₹1) |
| Overview status / amounts | `getLoanAccountOverviewDetails` with **`account_number_list`** | SUCCESS (e.g. 30223) |
| Statement force-bill / RSCH | `getLoanAccountStatement` | `DFC_PRTL_BILL` visible on death child; **not** on parent (Obs1b) |
| Payment amount vs principal | overview/statement + `loan_account_payments_details` | amount==principal OR documented legs |

## Fail-closed gates

- Registry `acceptance.dimensions` must include `downstream_ui`
- `ui_fields` must include **webapp-bound markers** (`getLoanAccountSummaryDetails`,
  `interest_details.accrued_amount`, `DFC_PRTL_BILL`, …) — SQL-only lists FAIL
  (`acceptance_coverage.py` `WEBAPP_UI_FIELD_MARKERS`)
- Anti-patterns: `webapp verified (partial)`, `overview-only verified`, `skip webapp APIs`
- DCF e2e: `assert_webapp_bound_apis` under `ACCEPTANCE_STRICT=1`

## Do not

- Claim "webapp verified" from DB-only asserts
- Call overview with bare `account_number` (returns 130015 — needs `account_number_list`)
- Invent parent `DFC_PRTL_BILL` to satisfy statement (Obs1b Out-of-scope)
