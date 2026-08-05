# Foreclosure local fixture — the four gates that block a real `loanPrepayment` run

**Trigger:** TDPQA-240 (2026-08-04). Six attempts were burned discovering these one at a time.
Check all four *before* building a foreclosure fixture.

## 1. `foreclosure_date` MUST equal today

`ValidateLoanPrepaymentDataProcessor.validateCurrentValueDate` throws **132282** unless
`foreclosure_date == systemDate`, both midnight-normalised — it rejects *earlier* and *later*.
`PlatformDateUtil.getSystemDate()` is `new Date()`, the wall clock; there is no settable
business-date row on local.

**Consequence:** you cannot age a loan to a future installment and foreclose there. A fixture
that needs FC *on an EMI date* must **disburse a loan whose EMI is today**
(`first_repayment_date = today midnight`, disburse ~60 days back). `plan_disburse_dates()`
always puts the first EMI strictly *before* today, so build the dates directly.

## 2. `loan_product.prepayment_allowed`

`ValidateLoanPrepaymentProductProcessor` throws **134144** when false; **134143** when
`minimum_installments_for_prepayment` / `minimum_repayment_ratio_for_prepayment` are unmet.
On local: product 44 (SHG, `loan_product.id=70`) and 45 (INDL, id 71) are `t`; **product 2 (JLG,
id 6) is `f`**.

The value is Redis-cached — a DB write alone does nothing, and **restarting accounting does not
help** because the cache lives in Redis DB 5, not in the JVM:

```bash
redis-cli -n 5 DEL "loan_product::LOCALACCOUNTINGLoanProductDAOService_findOneById_<id>" \
                   "loan_product::LOCALACCOUNTINGLoanProductDAOService_findLatestByProductId_<product_id>"
```

## 3. Maturity

**134291** — `foreclosure_date` cannot be >= maturity. Every long-lived local INDL loan has been
billed to maturity by past harness runs, so none of them can be foreclosed. Another reason the
fixture must be freshly disbursed.

## 4. SHG parent overdue

**433** "Cannot foreclose member loan as parent loan has overdue amount". When the group's own
first EMI is the same day, `settle_parent_overdue_before_vikram_fc` does not clear it. For a
defect that is not group-specific, **use INDL and avoid the gate entirely**.

## Pairs with

[[feedback_local_disburse_gst_simulator_block]] — the disburse itself is blocked until the fee
tax group is removed. See also [[feedback_dpic_harness_gotchas]].
