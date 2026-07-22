# CLB queue — duplicate REP_ACCT per member

## Symptom

`loan_account_events_queue` rows with `event_type='CLB'` and `event_status='P'` have members whose
`createLoanAccountRequest.disbursement_repayment_account_details` contains **two** entries with
`purpose[0].code='REP_ACCT'`.

## Root cause (proven)

1. LOS may send **more than one** `REP_ACCT` on a member’s `disbursement_repayment_account_details`.
2. Separately, `ChildLoanBookingEventsQueueDataPopulator` used to append parent `REP_ACCT` onto members that already had one (fixed: skip when `hasRepAcct`).

## Forward fix (L1)

- **Parent `disburseLoan` (SHG/JLG):** `CustomValidateDisbursementRepaymentAccountDetailsProcessor.validateMemberRepAcctUniqueness` — any member with `>1` `REP_ACCT` → `NovopayFatalException(134126)` during `populate_external_accounts` (before `createLoanAccountEventsProcessor` / CLB write).
- **CLB populator:** skip parent REP append when member already has REP; **do not** silently trim duplicates.
- **Backstop:** same CustomValidate on `createOrUpdateLoanAccount` still rejects poison queue rows that pre-exist.

## Poison rows (L0)

```bash
psql ... -v queue_id=402411 -f scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql
```

## Verify

```bash
ntest run disbursement.clb_rep_acct_dedupe_sim
```

Verify mode: **PROCESSOR_MIRROR_SIM** until live SHG CLB E2E fixture exists.
