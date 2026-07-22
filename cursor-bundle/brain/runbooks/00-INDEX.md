# Runbooks — production debugging by area

> Each runbook covers one class of production issue. Start with the **first SQL** to confirm the symptom, follow the decision tree, then fix at the right layer. **No runbook recommends DB writes outside the supported flows** — direct UPDATE on state columns leaves orphans.

## Index

| Runbook | When to use |
|---|---|
| [`clb-duplicate-rep-acct.md`](clb-duplicate-rep-acct.md) | CLB `loan_account_events_queue.data` members with duplicate `REP_ACCT` in `disbursement_repayment_account_details`. |
| [`disbursement-stuck.md`](disbursement-stuck.md) | LOS sent disburse, accounting not progressing or no result event |
| [`shg-jlg-children-missing.md`](shg-jlg-children-missing.md) | Parent loan ACTIVE but no child rows; or some children missing |
| [`repayment-mismatch.md`](repayment-mismatch.md) | Repayment posted but customer disputes split (PRIN/INT/PINT/FEE) |
| [`trial-balance-imbalance.md`](trial-balance-imbalance.md) | TB net non-zero on a GL after `trialBalanceCalculation` |
| [`eod-failed.md`](eod-failed.md) | EOD didn't run, ran partially, or any step in `runEODJobs` failed |
| [`npa-classification-incorrect.md`](npa-classification-incorrect.md) | DPD or NPA bucket looks wrong on a loan |
| [`kafka-consumer-lag.md`](kafka-consumer-lag.md) | Async Kafka consumer behind / stalled |
| [`maker-checker-stuck.md`](maker-checker-stuck.md) | Loan or master change stuck in `*_FREEZE` / approval pending forever |
| [`tenant-bootstrap.md`](tenant-bootstrap.md) | New tenant onboarding, missing API in routing, schema mismatch |
| [`webhook-replay.md`](webhook-replay.md) | Replaying a Kafka or HTTP callback safely (idempotency rules) |
| [`child-foreclosure-with-waiver.md`](child-foreclosure-with-waiver.md) | Child loan foreclosure with principal waiver — duplicate parent-leg postings, waiver propagation gaps, payment_details inconsistency. SDCP-10080. |
| [`shg-foreclosure-bpi-parent-child-parity.md`](shg-foreclosure-bpi-parent-child-parity.md) | SHG/JLG **parent** foreclosure BPI ≠ sum(children) for any N (SDCP-11058) — independent HALF_UP vs parent distribute. |
| [`pinpoint-rca-playbook.md`](pinpoint-rca-playbook.md) | **ANY** issue — the general symptom→decision-point→live-data method. Start here when no specific runbook matches. Pairs with `kg why <request>`. |
| [`charge-amount-shows-zero.md`](charge-amount-shows-zero.md) | A charge/fee/amount renders ₹0.00 or blank on a quote/preview (CBC fee, foreclosure fee, penal) — config-resolution (price-setup mapping `is_deleted`). |
| [`dcf-local-stack.md`](dcf-local-stack.md) | Local death-foreclosure insurance e2e — kafka, stubs, SQL placeholders, fixture backup/restore, `ntest run dcf.group_parent_last_child_e2e`. |
| [`sdcp-10199-group-parent-last-child-dfc.md`](sdcp-10199-group-parent-last-child-dfc.md) | SHG/JLG parent last-child DFC — PRIN paid not waived, account.status CLOSED, net_amount=0, **A2 EXTRA-net statement** + **B force-bill labd** (`5b1b928ed`), GAP-074 INT-180 still open. |
| [`../jira/JIRA-INDEX.md`](../jira/JIRA-INDEX.md) | **Smart JIRA graph** — ticket → domain/api → commits → ntest → reopen symptoms. Machine: [`../jira/jira-flow-graph.json`](../jira/jira-flow-graph.json). |
| [`mixed-train-matrix.md`](mixed-train-matrix.md) | **Mixed git trains** — DFC on 3.7.1 vs disburse on 3.4.2.2 vs DPI feature; scoped sync + `kg-switch` (never blind all-repo). |
| [`../workspace/ASK-TRACKER-2026-07-10.md`](../workspace/ASK-TRACKER-2026-07-10.md) | **Ask completeness tracker** (living) — OPEN/BLOCKED must block “done” claims. Twin: `ask-tracker-2026-07-10.json`. |

## Pinpoint RCA for ANY issue — start here

**Default for every analysis** (wrong / 0 / missing / stuck / duplicate / reverted value, or anything without a specific runbook): follow [`pinpoint-rca-playbook.md`](pinpoint-rca-playbook.md) and run **`kg why <request>`** first — observable → the resolver/decision-point that produced it → its config/state/master dependency → **verify each dependency LIVE before concluding (never assume a code↔config/state match)**. The specific runbooks below are just pre-worked instances of that method:

| Failure class (symptom) | Worked instance |
|---|---|
| **config_resolution** — a value/charge is 0/blank but data exists (resolver→master mapping `is_deleted`) | [`charge-amount-shows-zero.md`](charge-amount-shows-zero.md) · `kg why <charge>` |
| **race_condition** — value reverts / lost update after a transition | [`disbursement-stuck.md`](disbursement-stuck.md) · `kg why <request>` |
| **state_gate** — stuck in `*_FREEZE` / not progressing | [`maker-checker-stuck.md`](maker-checker-stuck.md) |
| **silent_catch** — "nothing happened", partial state, task never created | [`task-id-orphan-data-patch.md`](task-id-orphan-data-patch.md) |
| anything else | [`pinpoint-rca-playbook.md`](pinpoint-rca-playbook.md) · `kg why <request>` (every flow's silent decision-points) |

## Boundary rule

This is a **read-only diagnosis** environment. Any DB / Kafka / config change must be done in the appropriate target environment, not in darpan. The runbooks tell you *what* to change, not *where to write it from*.

## Cross-references

- LMS-internal scenarios (single-service): [`../accounting/10-debugging-runbook.md`](../accounting/10-debugging-runbook.md) — has 10 scenarios with first-SQL + decision tree
- Open High-risk gaps: [`../gaps-and-risks.md`](../gaps-and-risks.md)
- Older operational runbooks: [`../runbooks.md`](../runbooks.md) (single-file legacy; superseded by this folder for new content)
