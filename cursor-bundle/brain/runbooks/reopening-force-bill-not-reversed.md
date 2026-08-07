# Reopening — force bill left un-reversed (billing row + GL)

## Symptom

A loan was foreclosed, then reopened. The loan is `ACTIVE` again and the **closure** transaction is
reversed, but the **force bill** raised during foreclosure is still live:

- `loan_account_billing_details.reversed = false` on the partial-cycle (interest-only) row
- its `BILLING` / `NORMAL_BILLING` transaction has `transaction_master.reversed = false`, no
  `reversal_reference_number`, and its `transaction_details` legs stand un-contra'd

## First SQL

```sql
SELECT lacd.transaction_reference_number AS closure_ref, lacd.is_reversed AS closure_reversed
FROM mfi_accounting.loan_account_closure_details lacd WHERE lacd.loan_account_id = :account_id;

SELECT b.id, b.interest_amount, b.transaction_reference_number, b.reversed,
       tm.id AS txn_id, tm.reversed AS txn_reversed, tm.reversal_reference_number
FROM mfi_accounting.loan_account_billing_details b
LEFT JOIN mfi_accounting.transaction_master tm ON tm.reference_number = b.transaction_reference_number
WHERE b.account_id = :account_id AND b.principal_amount = 0
ORDER BY b.id DESC;
```

`closure_reversed = t` with any `reversed = f` interest-only row → this runbook.

## Root cause (fixed on `mfi_integration_v3.4.2.5` @ `df1662846`)

Reopening (`loanAccountReopening` `do_reopen`, `loans_orc.xml`) reversed exactly one transaction —
the ref that `initiateClosureReversalProcessor` puts in EC from `loan_account_closure_details`.
The force bill carries a **different** reference, so it was never in scope. `ReversalEngine` covers
`LoanDueDetails` / `LoanInstallmentDetails` / `WaiverDetails` only, and **no code path anywhere set
`LoanAccountBillingDetailsEntity.setReversed(true)`** — the column was write-once-false.

Impact beyond the stale flag: `LoanDueDetailsRepository` gates three queries on
`bd.reversed = false` (`:508`, `:514`, `:519`), so the installment keeps looking billed on the
reopened loan, and the gap interest stays booked in GL.

## The fix

- `reverseForceBillOnReopeningProcessor` runs after `updateLoanAccountClosureDetailsProcessor`.
  It reverses every open force bill on the reopened account and, when that account is an SHG child,
  the **parent mirror** raised for that child — matched on the mirror client reference
  `parentId + valueDate + childId` (`RegularForeclosureForceBillService` passes `child.getId()` as
  the discriminator). Each reversal goes through `reverseTransactionProcessor`, so GL contra legs
  come from the platform path, then the labd row flips to `reversed = true`.
- `ForceBillBillingSupport.persistForceBillBillingDetails` writes **one labd row per force-bill
  transaction**. It used to accumulate parent contributions into a single row (`FC 17 + DFC 11 → 28`)
  and overwrite the transaction ref, which destroyed the link back to each child and made
  child-level reversal impossible.

## Things that stay true

- **DFC needs no reversal path** — a death-foreclosed LAN cannot be reopened. The un-merge matters
  there only so a DFC contribution survives an FC sibling's reopening.
- **Siblings must not move.** Reversing a child's reopening must leave other children's parent
  contributions at `reversed = false`.
- **Pre-existing merged rows are not retro-split.** Rows written before `df1662846` still hold a
  combined amount with the last child's ref; those need an ops patch, not a code path.

## Verify

```bash
ntest run flowtest.loan_reopening      # assert_force_bill_reversed_on_reopen
ntest run dcf.group_parent_last_child_e2e
```

Expected: `force-bill reversal PASS: child=N→0 parent_mirror=N→0 other_children_untouched=K txn_reversed=all`.

Found during TDPQA-72 regression; QA4 evidence LAN `6002270025` (account `7047662`) — closure
`is_reversed=t`, labd `163202` and txn `1970684` left open.
