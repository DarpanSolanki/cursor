# Edge: SHG/JLG parent stays open / wrong amounts after last-child death foreclosure

**Symptom:** After insurance approve closes the last ACTIVE group child, parent still `loan_status=ACTIVE`, or `account.status=ACTIVE` while loan CLOSED, or next EMI still on Loan 360, or statement principal ≈ 2× RSCH txn, or parent PRIN pending ≠ 0 / PRIN waived instead of paid, or **parent RSCH amount = full POS while child claim had EXTRA** (parent/child mismatch), or **force-bill without labd / txn_ref**.

**Canonical trains:**
- Closure series: `mfi_integration_v3.7.1` (contains 3.4.2.1/2/3 SDCP-10199).
- **A2 EXTRA-net + B force-bill labd:** `mfi_integration_v3.4.2.4` @ `5b1b928ed` (GAP-075 RESOLVED).

**Code:** `DeathForeclosureInsuranceWriter.doParentPartPrePayment` + `finalizeParentClosureOnLastChildDfc` + `forceBillPartialCycleInterest`; overview `GetLoanAccountInstallmentDetailsProcessor.isLoanClosed(loan_status, account_status)`.

**Correct contract:** last child → pay parent POS (not waive PRIN); `net_amount=0` before payment-details save; close loan **and** account; **EXTRA-net** parent TRANSACTION_AMOUNT/UNBLD_PRIN when claim has EXTRA; force-bill **labd** linked to `DFC_PRTL_BILL_*`.

**Verify:** `ntest run dcf.group_parent_last_child_e2e` · runbook `cursor-bundle/brain/runbooks/sdcp-10199-group-parent-last-child-dfc.md`.

**Still open:** GAP-074 INT-180 (parent INT pending after CLOSE) — parked; do not conflate with A2/B.

**Anti-pattern:** calling / reintroducing a “waive all future parent dues” helper — that was unused dead code and wrong for PRIN. Shipping code without updating registry note + runbook + gaps — see `feedback_post_ship_registry_runbook_gap_mandatory.md`.
