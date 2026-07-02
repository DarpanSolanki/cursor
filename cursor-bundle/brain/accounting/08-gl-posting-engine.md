# 08 · GL posting engine — how a transaction becomes a DR/CR pair

> **Why this file:** the previous docs reference `postTransaction` and "GL hit" without explaining how the system actually decides which GL is debited and which is credited. That decision involves five master tables and three engines, all wired through a single processor (`ExecuteTransactionRulesProcessor`). Understanding this is the difference between "I see a wrong DR/CR" and "I know which row in `transaction_accounting_rule` to fix".

---

## 1. The five masters that drive every GL hit

| Master table | Java entity | What it defines |
|---|---|---|
| `transaction_catalogue` | [TransactionCatalogueEntity](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/entity/TransactionCatalogueEntity.java) | A *named transaction* (e.g. `LOAN_DISB_PRIN`, `LOAN_REP_INT`, `PENAL_INT_BOOK`). Every `postTransaction` call carries a `transaction_catalogue_id`. |
| `transaction_accounting_rule` | [TransactionAccountingRuleEntity](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/accountingrules/entity/TransactionAccountingRuleEntity.java) | One row per "leg" of the transaction. Holds: source-amount key, debit placeholder, credit placeholder, fallback credit placeholder, entry type, entry sub-type, condition expression, narration templates. |
| `placeholder_master` | [PlaceholderMasterEntity](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/placeholdermaster/entity/PlaceholderMasterEntity.java) | A *symbolic account name* (e.g. `BANK_AC`, `LOAN_PRINCIPAL_AC`, `INTEREST_INCOME_AC`) with two flags: `isActorAccount`, `isExternallyPassedAccount`. |
| `product_transaction_catalogue_placeholder` | [ProductTransactionCataloguePlaceholderInternalAccountDefinitionEntity](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/entity/ProductTransactionCataloguePlaceholderInternalAccountDefinitionEntity.java) | The *binding* — for product P + transaction-catalogue T + placeholder X, what `internal_account_definition_id` (and which GL code) does X resolve to? This is the only product-specific master here. |
| `internal_account` | [InternalAccountEntity](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/internalaccount/entity/InternalAccountEntity.java) | The *physical* office-scoped account instance backing an `internal_account_definition`. Resolved by `(office_id, internal_account_definition_id)`. |

Plus the GL itself:

- `general_ledger` — the chart of accounts. `code` is what shows up on the trial balance.
- `child_general_ledger` — a parallel ledger keyed off the parent GL; entries get a code prefixed with `CG` for child loan transactions ([ChildGeneralLedgerEntity.CHILD_GL_CODE_PREFIX](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/generalledger/entity/ChildGeneralLedgerEntity.java#L25)).

---

## 2. The `postTransaction` Request — top-level pipeline

[product_transaction_orc.xml:3-37](../../novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml#L3-L37)

```
postTransaction
  ├── validateTransactionDataProcessor
  ├── populateAdditionalInformationProcessor
  ├── populateAndValidateAccountDetailsProcessor   ← resolves account_number → AccountDTO into ExecutionContext
  ├── populateAdditionalAmountProcessor
  ├── clientReferenceNumberDedupProcessor          ← idempotency check (table: transaction_master)
  ├── getTransactionCatalogueIdProcessor           ← maps transaction_catalogue_code → id
  ├── getTransactionRuleListProcessor              ← loads List<TransactionAccountingRuleEntity> for that catalogue id
  ├── executeTransactionRulesProcessor             ← THE engine, see §3 below
  └── if run_mode = TRIAL: validate balance + build response (no DB write)
       if run_mode = REAL:
            generateTransactionReferenceNumberProcessor
            createTransactionMasterProcessor       ← INSERT transaction_master row
            createTransactionMetadataProcessor     ← INSERT transaction_metadata
            createTransactionPartitionDetailsProcessor  ← INSERT N rows into transaction_partition_details
            createTransactionDetailsProcessor      ← INSERT account-level transaction_details + balance updates
            createTransactionResponseProcessor
```

Every accounting flow that "hits the GL" — disbursement, repayment, accrual booking, foreclosure, charge waiver, manual JE — funnels through this exact chain. The differences between flows are purely in **which transaction_catalogue_code** they use and **what amounts they put in the ExecutionContext** before calling `postTransaction`.

The `<API id="postTransaction">` calls that show up everywhere in the orchestration XMLs (e.g. the `loanRepayment`, `disburseLoan`, `childLoanRepayment` Requests) all funnel back here.

---

## 3. `ExecuteTransactionRulesProcessor` — the engine itself

Source: [ExecuteTransactionRulesProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java)

Two phases:

### Phase 1 — `calculateComponentsInTransactionRules` (lines 87-230)

For each `TransactionAccountingRuleEntity` row in the catalogue's rule list, in `sequence_number` order:

1. **Resolve placeholders to accounts.** `resolvePlaceholder(...)` (line 233) does this for the debit, credit, and (optional) fallback-credit placeholders. The resolution rules (in priority order):
    - If the placeholder's `isActorAccount = true` → take the account number from `executionContext.getValue(placeholder.code)`. The account is the *customer's* account passed in by the caller. Add to `actorAccountSet`.
    - If `isExternallyPassedAccount = true` → take from ExecutionContext like above (no actor side-effect).
    - Otherwise → **product/catalogue lookup**: query `product_transaction_catalogue_placeholder` for `(product_id, transaction_catalogue_id, placeholder.code)` → returns `(internal_account_definition_id, gl_code, product_type)`. Then `internal_account` lookup by `(office_id or default_office_id, internal_account_definition_id)` → physical `internal_account.code`. The `gl_code` is what gets written on the partition row. Throws `134207` if no rule binding exists, `134182` if the office has no internal_account instance.
2. **Compute the amount.** Two paths:
    - `condition_type = "ARITHMETIC_CONDITION"` → evaluate the SpEL expression in `condition_expression` against the ExecutionContext (line 403-408). The ExecutionContext exposes every value that earlier processors have populated, e.g. `${principal_amount}`, `${interest_amount}`. The result is stored at the `source_amount` key.
    - Otherwise → `source_amount` is read directly from the ExecutionContext (a string or BigDecimal).
3. **Compute the entry.** Two paths:
    - `entry_type = "TRANSFER"` → no extra computation, `calculatedAmount = sourceAmount`, no tax.
    - Else → look up a Spring bean named `<lower(entry_type)>Engine` and call `compute(executionContext, request)`. The two ComputeEngine implementations are:
        - `priceEngine` → [PriceEngine.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/core/PriceEngine.java) — for charges/fees, walks `price_setup` slabs against `product_scheme_transaction_accounting_rule_price_setup`, then applies a `PricingStrategy` (`SystemComputedPricingStrategy` or `ExternalPricingStrategy`).
        - `taxEngine` → [TaxEngine.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/core/TaxEngine.java) — for tax components, walks `tax_component_slab` and dispatches to one of `InclusiveTaxCalculator`, `ExclusiveTaxCalculator`, `PrecalculatedTaxComputationStrategy`, etc.
4. **Persist intermediate values.** The computed amount + tax amount are placed back in the ExecutionContext under the rule's `reference_code`, so later rules (sequenced after this one) can read them with `${reference_code}` in their own `condition_expression`. **This is how multi-leg transactions chain together.**
5. **Build a `TransactionRuleDTO`** with the resolved debit/credit/fallback account numbers, GL codes, source/calculated amounts, narrations, part-info fields, and append it to `transaction_rule_dto_list`.

### Phase 2 — `executeTransactionRules` (lines 329-365)

For each `TransactionRuleDTO` whose `calculatedAmount != 0`:

1. **Update the in-memory `accountingMap`**: subtract `calculatedAmount` from the debit account's net, add to the credit account's net. (Used for trial-balance pre-flight checks.)
2. **Emit two `TransactionPartitionDetailsEntity` rows** — one DR, one CR, each carrying:
    - `account_number`, `gl_code`, `currency`, `amount`, `source_amount`
    - `cr_dr_indicator` (`D` or `C`)
    - Three `part_info_*` fields with placeholder substitution against the ExecutionContext
    - `narration` (template substituted)
    - `entity_id` and `entity_type` (e.g. loan_account_id + "LOANS")
    - **For child loan transactions** (`is_child_account = true` in the ExecutionContext): `gl_code = "CG" + gl_code` so the row hits `child_general_ledger` instead of `general_ledger` ([line 391-393](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ExecuteTransactionRulesProcessor.java#L391-L393)).
3. The full list goes into the ExecutionContext as `transaction_partition_details_list`. `createTransactionPartitionDetailsProcessor` (next in the pipeline) is what bulk-INSERTs these into `transaction_partition_details`.

---

## 4. Worked example — a single-leg loan repayment (interest)

Suppose the caller has set:
```
account_number       = LAN0001234   (customer's loan account)
transaction_catalogue_code = LOAN_REP_INT
interest_amount      = 1500
office_id            = 7
run_mode             = REAL
```

And the catalogue `LOAN_REP_INT` has one rule:
```
sequence_number             = 1
source_amount               = "interest_amount"
debit_account_placeholder   = "BANK_AC"           (isActorAccount=false; bound via product_transaction_catalogue_placeholder to internal_account_definition "BANK_RECEIVABLE", GL "210101")
credit_account_placeholder  = "INT_INCOME_AC"     (bound to internal_account_definition "INT_INCOME", GL "410101")
entry_type                  = "TRANSFER"
reference_code              = "REP_INT"
condition_type              = (null)
```

Then `ExecuteTransactionRulesProcessor` produces:

| Side | Account number | GL code | Amount |
|---|---|---|---|
| DR | (instance of BANK_RECEIVABLE for office 7) | `210101` | 1500 |
| CR | (instance of INT_INCOME for office 7) | `410101` | 1500 |

If the caller instead set `is_child_account = true` (because this was a child-loan repayment), the GL codes become `CG210101` and `CG410101`.

If the rule had `entry_type = "TAX"` and `entry_sub_type = "GST"`, the engine would have invoked `taxEngine.compute(...)` instead of `TRANSFER`, computed GST on top of `interest_amount`, and additional rule DTOs for the GST legs would be appended via `additionalTransactionRuleDTOList`.

---

## 5. The "fallback credit" path

Some catalogues need to credit account A *if it has capacity*, otherwise account B. Example: write-off — credit the principal-receivable normally, but if the loan is in suspense, credit the suspense GL instead. The `fallback_credit_placeholder` field on `transaction_accounting_rule` resolves the fallback the same way as the primary credit. Today the engine resolves it eagerly (line 144-149) but the **decision of which one to use** is the responsibility of the calling Request's processors — they set the appropriate `*_amount` keys in the ExecutionContext to zero the path that shouldn't fire.

---

## 6. How earlier processors prepare the engine

The processors that run *before* `executeTransactionRulesProcessor` exist purely to populate the ExecutionContext keys that the engine reads:

| Processor | What it puts into the ExecutionContext |
|---|---|
| `populateAndValidateAccountDetailsProcessor` | `<account_number> → AccountDTO` (incl. product_id) |
| `populateAdditionalAmountProcessor` | named amount keys (e.g. `principal_amount`, `interest_amount`, `fee_amount`) |
| `populateAdditionalAmountDetailsProcessor` (used inside loanRepayment etc.) | per-component amounts post-appropriation |
| `populateTransactionAccountDetailsProcessor` | resolves and exposes any actor-account references the catalogue uses |
| `getTransactionCatalogueIdProcessor` | `transaction_catalogue_id` |
| `getTransactionRuleListProcessor` | `transaction_rule_list` (the list the engine iterates) |

If a flow's GL hit looks wrong, the **first place to look** is which keys these processors set, not the engine itself. The engine almost never has bugs; the calling flow almost always does.

---

## 7. The repayment-appropriation step (preceeds posting)

For a `loanRepayment` / `childLoanRepayment`, before `postTransaction` is called, the amount must be split across due components (principal, interest, penalty, fee). That happens in [RepaymentApproppriationProcessor.java](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java).

Algorithm (verified against [process()](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/repayment/processor/RepaymentApproppriationProcessor.java#L64-L121)):

1. Look up `loan_product_asset_criteria` for the loan's product + current asset-criteria slab → returns `(comp1, comp2, comp3, comp4, liquidationOrder)`. Each `comp*` is one of `APP_LOGIC_PRIN`, `APP_LOGIC_INT`, `APP_LOGIC_PNLT`, `APP_LOGIC_FEES` (codes in [AccountingConstants.java:37-40](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/common/AccountingConstants.java#L37-L40)). The order of those four columns IS the appropriation precedence.
2. Sort `loan_due_details_list` by `liquidationOrder`:
    - `LIQ_INSTL` → installment first (due_date), then component
    - `LIQ_COMP` → component first, then due_date
    - `LIQ_INSTL_CHRG_COMP` → split into installment-due (`PRIN`/`INT`) and charge-due (`PINT`/`FEE`) lists; installments by date, charges by component
3. Walk the sorted list, deducting the repayment amount from each due row, accumulating into `RepaymentComponents{principal, interest, penalty, fee, amountRemaining}`.
4. Round the leftover via `currencyUtil.roundAmount(...)` — this is the `excess_amount` that goes into `loan_account_payments_details` for later auto-clearance against next dues.
5. If the loan has `npa_ageing_start_date != null`, set `suspense_amount = interest_amount` — this signals downstream processors to credit the suspense GL instead of interest income.

After this processor runs, the per-component keys (`principal_amount`, `interest_amount`, `penalty_amount`, `fee_amount`, `excess_amount`, `suspense_amount`, `total_settled_amount`) are in the ExecutionContext. The next processors (`updateLoanDueDetailsProcessor`, `updateLoanInstallmentDetailsProcessor`, `populateAdditionalAmountDetailsProcessor`) then prepare the catalogue + rule context, and finally `postTransaction` is called.

---

## 8. Component-code dictionary

Used everywhere — internalise these:

| Code | Meaning |
|---|---|
| `PRIN` | Principal |
| `INT` | Regular interest |
| `PINT` | Penal interest |
| `FEE` | Fee / charge |
| `APP_LOGIC_PRIN` | Appropriation precedence slot for principal |
| `APP_LOGIC_INT` | Appropriation precedence slot for interest |
| `APP_LOGIC_PNLT` | Appropriation precedence slot for penalty |
| `APP_LOGIC_FEES` | Appropriation precedence slot for fees |
| `LIQ_INSTL` | Liquidate by installment date first |
| `LIQ_COMP` | Liquidate by component (across installments) first |
| `LIQ_INSTL_CHRG_COMP` | Installments by date, then charges by component |

---

## 9. Things that go wrong — and where the bug lives

| Symptom | Likely cause | Where to look |
|---|---|---|
| Wrong GL on one leg | Wrong placeholder binding for that product | `product_transaction_catalogue_placeholder` row |
| Trial balance off by exactly the txn amount | A rule's debit and credit placeholder both resolve to the same internal account | `placeholder_master.is_externally_passed_account` flag on one side wrongly true |
| Leg missing entirely | `condition_type=ARITHMETIC_CONDITION` evaluated to zero so the rule was skipped (line 343) | `condition_expression` in the rule, plus the ExecutionContext keys it references |
| Child-loan posting hit `general_ledger` instead of `child_general_ledger` | Caller forgot to set `is_child_account=true` | calling Request's `populateAdditionalInformationProcessor` IParams |
| `134207` thrown | No `product_transaction_catalogue_placeholder` row for `(product_id, transaction_catalogue_id, placeholder_code)` | the binding table |
| `134182` thrown | No `internal_account` instance for `(office_id, internal_account_definition_id)` and no default-office override either | check `internal_account` table for that office, or `loan.internal.account.default.office.id` config (default `1`) |
| Tax came out as zero on a fee | TaxEngine ran but `tax_component_slab` returned no slab match for the source amount | `tax_component_slab` rows for that tax component |
| Same `client_reference_number` rejected | Idempotency dedup ([clientReferenceNumberDedupProcessor](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ClientReferenceNumberDedupProcessor.java)) found a prior `transaction_master` row | by design — caller must pass a fresh ref |

---

## 10. Tables written by `postTransaction` (REAL mode)

Per call:

- 1 row in `transaction_master` (the txn header — ref no, status, amount, currency, catalogue id, client ref no)
- 1 row in `transaction_metadata` (free-form key/value bag from the caller)
- N rows in `transaction_partition_details` (one per rule × 2 for DR/CR; gl_code, account_number, amount, narration, part_info_1..3)
- N rows in `transaction_details` per affected `account_number` (account-level ledger rows; balances on `account_balance` are updated in lock-step)
- 1 row in `audit_log` (framework-emitted, via `<AuditData>` on the Request)

Reversal (`reverseTransaction` Request) emits a sibling set with `cr_dr_indicator` flipped, linked back to the original via `transaction_reversal_document`.
