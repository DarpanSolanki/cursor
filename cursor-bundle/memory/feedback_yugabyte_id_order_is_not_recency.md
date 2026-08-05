# `ORDER BY id DESC` is not "most recent" on Yugabyte

**Trigger:** TDPQA-240 (2026-08-04). `assert_last_child_parent_closure.py` compared the group's
payment row against the last member's via `ORDER BY id DESC LIMIT 1` on
`loan_account_payments_details`. It passed on one run and failed on the next with *identical*
money, and cost a full rebuild-and-rerun to attribute.

## Why

Yugabyte allocates sequence values from **cached blocks per session/node**, so ids are not
monotonic in creation time. A row written earlier can carry a higher id than one written later:

```
child 6004176427: id 394306 created 21:38:43 -> 14871 (the foreclosure)
                  id 394403 created 21:37:36 -> 3426  (earlier, but HIGHER id)
child 6004177027: id 394601 created 21:41:26 -> 3426
                  id 394801 created 21:42:33 -> 14871
```

The tip assert therefore compared the closure against whichever row won the id race. Same code,
same amounts, opposite verdicts.

## Rule

Never pick "the row this flow wrote" by max id. Anchor on something the flow owns:

1. **best** — the posting's own `transaction_reference_number` (join through
   `transaction_master.reference_number`)
2. acceptable — `ORDER BY created_on DESC, id DESC` as a fallback only
3. never — `ORDER BY id DESC LIMIT 1` alone

This compounds the tip-only problem already in `40-knowledge-upkeep.md`: auditing one row misses
the rows QA opens, *and* on Yugabyte you may not even be auditing the row you think you are.

## Pairs with

[[feedback_force_bill_double_bills_already_billed_cycle]] ·
[[feedback_foreclosure_local_fixture_gates]]
