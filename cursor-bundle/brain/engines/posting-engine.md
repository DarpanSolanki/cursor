# Posting engine — `postTransaction` / `reverseTransaction` deep reference

**Branch verified:** `mfi_integration_v3.3.1.0.1` (head `149009993`, audited 2026-05-08).
**3.3.1.0.1 delta:** dedup error code changed from `134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)` → `134497` in commit `d358a9034` (`SDCP | Return friendly error for duplicate client_reference_number on loanRepayment`). Both codes appear below — `134497` is the current canonical value; `134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)` only on `3.2.8.4.1` and earlier.
**Authoritative paths:**
- ORC: [product_transaction_orc.xml](../novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml)
- Java root: [src/main/java/in/novopay/accounting/transaction/](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/)

This file is the single deep reference for the ledger spine. `accounting-flows.md` summarizes; this file shows every processor's I/O contract so a fix can be designed without re-reading code.

---

## 1. Engine surface (12 Requests in `product_transaction_orc.xml`)

| Request | Lines | One-line purpose |
|---------|------:|------------------|
| `postTransaction` | 3–34 | Ledger posting (TRIAL or REAL) — the canonical money engine |
| `getAccountBalances` | 36–42 | Balance enquiry |
| `getAccountStatement` | 44–63 | Statement extract |
| `getTransactionPartitionDetails` | 65–78 | Partition detail enquiry |
| `reverseTransaction` | 80–91 | Inverts a posted txn (Cr/Dr swap, links via `reversal_reference_number`) |
| `getCurrencyMasterDetails` | 93–112 | Currency lookup |
| `getLoanAccountStatement` | 114–152 | Loan statement (regular or export) |
| `postManualJournalEntry` | 154–435 | Maker-checker MJE flow (DEFAULT/BULK/RESUBMIT/APPROVE/REJECT) |
| `reverseManualJournalEntry` | 438–567 | Reverses MJE; routes through `reverseTransactionProcessor` on APPROVE |
| `glBalanceZeroisation` | 569–600 | Year-end GL zero-out — bypasses dedupe + rules; goes straight to master/partition/details |
| `executeLMSPortfolioTransfer` | 602–621 | Single processor (`executeLMSPortfolioTransferProcessor`) |
| `doGLTransfer` | 623–640 | Inter-branch GL transfer (`doGLTransferProcessor`) |

---

## 2. `postTransaction` chain — verbatim verified

```3:34:novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml
<Request name="postTransaction">
    <Processors>
        <Processor bean="validateTransactionDataProcessor" />
        <Processor bean="populateAdditionalInformationProcessor" />
        <Processor bean="populateAndValidateAccountDetailsProcessor" />
        <Processor bean="populateAdditionalAmountProcessor" />
        <Processor bean="clientReferenceNumberDedupProcessor" />
        <Processor bean="getTransactionCatalogueIdProcessor" />
        <Processor bean="getTransactionRuleListProcessor" />
        <Processor bean="executeTransactionRulesProcessor" />
        <Control method="regExp" pattern="${run_mode}" condition="=" value="TRIAL">
            <Processor bean="populateLimitRequestProcessor" />
            <Processor bean="validateActorAccountBalanceProcessor" />
            <Processor bean="createTransactionResponseProcessor" />
            <Processor bean="validateLimitProcessor" />
        </Control>
        <Control method="regExp" pattern="${run_mode}" condition="=" value="REAL">
            <Processor bean="generateTransactionReferenceNumberProcessor" />
            <Processor bean="createTransactionMasterProcessor" />
            <Processor bean="createTransactionMetadataProcessor" />
            <Processor bean="createTransactionPartitionDetailsProcessor" />
            <Processor bean="createTransactionDetailsProcessor" />
            <Processor bean="createTransactionResponseProcessor" />
        </Control>
    </Processors>
</Request>
```

### Processor I/O contract (Java verified — package `in.novopay.accounting.transaction.processor`)

| # | Processor (bean) | Reads from EC | Writes to EC / DB | DAO calls | Throws (NovopayFatalException) |
|---|------------------|---------------|-------------------|-----------|-------------------------------|
| 1 | `validateTransactionDataProcessor` | `run_mode`, `function_code`, `function_sub_code`, `receipt_number`, `amount`, currency | (validation only) | `CurrencyUtil` | 11008, 11012, 11013, 134252, 132160 |
| 2 | `populateAdditionalInformationProcessor` | `additional_information_details[]` | unpacks array → context kv pairs | — | — |
| 3 | `populateAndValidateAccountDetailsProcessor` | `account_details[]`, placeholder codes | per-placeholder `AccountDTO`; placeholder→code map | `AccountDAOService`, `InternalAccountDAOService`, `PlaceholderMasterDAOService` | 134065 (duplicate placeholder); ⚠ no null check on `account_details` (GAP-063 risk) |
| 4 | `populateAdditionalAmountProcessor` | `additional_amount_details[]` | `reference_code`→amount map | — | 134094 (reserved key collision) |
| 5 | `clientReferenceNumberDedupProcessor` | `client_code`, `client_reference_number` | (dedupe gate) | `TransactionMasterDAOService.findOneByClientCodeAndClientReferenceNumber` | **134497** on `3.3.1.0.1+` / `134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)` on `3.2.8.4.1` — the canonical idempotency gate ([`ClientReferenceNumberDedupProcessor.java:34`](../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/transaction/processor/ClientReferenceNumberDedupProcessor.java#L34)) |
| 6 | `getTransactionCatalogueIdProcessor` | `transaction_type`, `transaction_sub_type` | `transaction_catalogue_id`, `transaction_category_list` | `TransactionCatalogueDAOService.findByTypeAndSubType` | — |
| 7 | `getTransactionRuleListProcessor` | `transaction_catalogue_id` | `transaction_rule_list` | `TransactionAccountingRuleDAOService.findByTransactionCatalogueId` | — |
| 8 | `executeTransactionRulesProcessor` | `transaction_rule_list`, `transaction_catalogue_id`, account/placeholder map, metadata | **`accounting_map`** (`LinkedHashMap<account, AccountingSummaryDTO>` with `netAmount`, `balanceAfterTransaction`, `CrDrIndicator`); `transaction_partition_details_list` | `ComputeEngine`, `PriceEngine`, `TaxEngine`, `PlaceholderMasterDAOService`, `ProductTransactionCatalogueDAOService`, `InternalAccountDefinitionDAOService`, `ChildGeneralLedgerEntity` | SpEL evaluation errors |
| **TRIAL branch** ||||||
| 9T | `populateLimitRequestProcessor` | `actor_account_list` | `limits_to_validate[]` | — | — |
| 10T | `validateActorAccountBalanceProcessor` | `accounting_map`, `actor_account_list` | updates `AccountBalanceEntity.availableBalance` in-memory | `AccountBalanceDAOService.findByAccountNumberForTransactionValidation` | **134066** (insufficient balance), **134077** (max exceeded) |
| 11T | `createTransactionResponseProcessor` | `transaction_partition_details_list`, `actor_account_list`, `accounting_map` | response JSON | `CurrencyUtil` | — |
| 12T | `validateLimitProcessor` | `limits_to_validate[]` | (remote validation) | `NovopayInternalAPIClient` → `validateLimits` | API errors |
| **REAL branch** ||||||
| 9R | `generateTransactionReferenceNumberProcessor` | — | `transaction_reference_number` (Julian-date `YYDDD` + UUID) | — | — |
| 10R | `createTransactionMasterProcessor` | user/audit fields, catalogue id, refs, currency, amount, value_date, remarks, receipt | `transaction_master_id`; normalized `value_date` | `TransactionMasterDAOService.save` | — |
| 11R | `createTransactionMetadataProcessor` | `metadata[]` | (rows persisted) | `TransactionMetadataDAOService.save` | — |
| 12R | `createTransactionPartitionDetailsProcessor` | `transaction_partition_details_list` | `account_gl_map` (account→glCode); FK on rows | `TransactionPartitionDetailsDAOService.save` | — |
| 13R | `createTransactionDetailsProcessor` | `transaction_master_id`, `accounting_map`, `value_date`, `originating_office_id`, `office_id`, `account_gl_map`, `is_child_account` | (rows persisted with Cr/Dr indicator) | `TransactionDetailsDAOService.save` | — |
| 14R | `createTransactionResponseProcessor` | (as above) | response JSON | — | — |

**Plain English (REAL):** validate → expand placeholders → dedupe by client ref → load catalogue + rules → run rules engine → mint ref number → persist `transaction_master` (header) → `transaction_metadata` (kv tags) → `transaction_partition_details` (line-level partitions with GL codes) → `transaction_details` (Cr/Dr legs) → respond.

**Plain English (TRIAL):** same up to rules → build limit request → validate balances in-memory → build response → call `validateLimits` API. **No DB writes** beyond what the rules read.

---

## 3. `reverseTransaction` chain

```80:91:novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml
<Request name="reverseTransaction">
    <Processors>
        <Processor bean="reverseTransactionProcessor" />
    </Processors>
</Request>
```

**Class:** `transaction/reverse/processor/ReverseTransactionProcessor.java`.

Lookup priority:
1. `transaction_reference_number` if provided.
2. else `client_reference_number`.

Effects:
- Loads original `transaction_master` + partition + details.
- Sets original `reversed=true`, `reversal_reference_number=<new>`.
- Inserts a new `transaction_master` row with `reversal=true` and a fresh ref number.
- Inserts mirror `transaction_partition_details` and `transaction_details` rows with **flipped CrDr**.

Throws:
- **130121** — neither ref provided.
- **132161** — original not found.
- **134071** — original already reversed.

---

## 4. `glBalanceZeroisation` — bypass route

```569:600:novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml
```

Chain (intentionally **not** going through `clientReferenceNumberDedupProcessor` / rules / engines):
- `getTransactionCatalogueIdProcessor`
- `generateTransactionReferenceNumberProcessor`
- `createTransactionMasterProcessor`
- `createPartitionDetailsForGLZeroisation` (custom partition builder)
- `createTransactionPartitionDetailsProcessor`
- `createTransactionDetailsProcessor`

**Implication:** any feature that depends on dedupe/rule semantics (e.g. NPA reverse, limit checks) is **not active** for year-end zeroisation — fix has to be local to this Request, not the generic engine. No `src/test` coverage — flagged in `gaps-and-risks.md`.

---

## 5. Manual Journal Entry — flow shape (lines 154–567)

`postManualJournalEntry` has 5 modes via outer `<Control>` on `function_code`:
- `DEFAULT` (maker create) — validate → persist draft if maker-checker, else go to engine.
- `BULK` — bulk file ingest path.
- `RESUBMIT` — re-edit + resubmit.
- `APPROVE` — runs the actual posting: `clientReferenceNumberDedupProcessor` → `getTransactionCatalogueIdProcessor` → `generateTransactionReferenceNumberProcessor` → `createTransactionMasterProcessor` → `createTransactionMetadataProcessor` → `createPartitionDetailsForManualJournalPostingProcessor` → `createTransactionPartitionDetailsProcessor` → `createTransactionDetailsProcessor`.
- `REJECT` — marks draft rejected.

`reverseManualJournalEntry` mirrors this; only `APPROVE` actually invokes `reverseTransactionProcessor`.

**Dedupe semantics for MJE:** uses the same `clientReferenceNumberDedupProcessor` — duplicate-MJE gate (134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)) applies.

---

## 6. Entity mapping (verified — package `transaction/entity/`)

| Entity | Table | Notable columns |
|--------|-------|-----------------|
| `TransactionMasterEntity` | `transaction_master` | `id`, `transaction_catalogue_id`, **`reference_number`** (unique), **`client_reference_number`** (NOT NULL — dedupe), `client_code`, `currency`, `original_amount`, `status`, `business_date`, `transaction_value_date`, `reversed`, `reversal`, `reversal_reference_number`, audit cols |
| `TransactionDetailsEntity` | `transaction_details` | `id`, `transaction_id` (FK), `originating_office_id`, `office_id`, `account_number`, `gl_code`, `value_date`, `business_date`, `currency`, `net_amount`, `cr_dr_indicator` (C/D), `narration` |
| `TransactionPartitionDetailsEntity` | `transaction_partition_details` | `id`, `transaction_id`, `reference_code`, `account_number`, `currency`, `amount`, `source_amount`, `cr_dr_indicator`, `gl_code`, `office_id`, `entity_type`, `entity_id`, `part_info_1/2/3`, `narration`, `display_flag`, `is_child_gl_code` |
| `TransactionMetadataEntity` | `transaction_metadata` | `id`, `transaction_id`, `label`, `value` |
| `TransactionCatalogueEntity` | `transaction_catalogue` | `id`, `type`, `sub_type`, `type_name`, `sub_type_name`, `transaction_mode`, `is_reversible`, audit cols |
| `TransactionCategoryEntity` | `transaction_category` | `id`, `code`, `name`, `description` |
| `TransactionAccountingRuleEntity` | `transaction_accounting_rule` | `id`, `transaction_catalogue_id`, `sequence_number`, `entry_type`, `entry_lookup_code`, `reference_code`, `source_amount`, `debit_account_placeholder`, `debit_narration`, `credit_account_placeholder`, `credit_narration`, `fallback_credit_placeholder`, `condition_type`, `condition_expression` |

---

## 7. Where `postTransaction` is called from (13 ORC call-sites)

`postTransaction` is invoked nested as `<API>` from many flows — full enumeration in `.cursor/skills/accounting-knowledge/flows.md`. The recurring shape:

```xml
<API id="postTransaction" name="postTransaction" version="v1">
    <IParam fieldName="transaction_type" value="LOAN_REPAYMENT" scope="local"/>
    <IParam fieldName="transaction_sub_type" value="${repayment_mode}" scope="local"/>
    <IParam fieldName="amount" value="${repayment_amount}" scope="local"/>
    <IParam fieldName="client_reference_number" value="${receipt_number}" scope="local"/>
    <IParam fieldName="run_mode" value="REAL" scope="local"/>
</API>
```

Major callers (Request → typical txn-type):
- `loanRepayment` → `LOAN_REPAYMENT` (+ NPA reverse leg with sub-type `NPA`)
- `childLoanRepayment` → `LOAN_REPAYMENT` (per-member)
- `disburseLoan` → `LOAN_DISBURSEMENT` / sub-type CASH | CASA | ACCOUNT_TRANSFER_NEFT
- `loanPrepayment` / `loanWriteoff` → `LOAN_WRITE_OFF` / `FINAL_WRITE_OFF`
- `loanDisbursementCancellation` → `LOAN_DISBURSEMENT_CANCELLATION`
- `loanAccountExcessAmountRefund` → `EXCESS_AMT_REFUND`
- `loanAccountRebooking` / `childLoanRebooking` → `LOAN_REBOOKING` / `INTEREST_ADJUSTMENT`
- Death foreclosure writer → `DEATH_FORECLOSURE` / `DEFAULT`
- Interest accrual booking → `INTEREST` / various
- Insurance writers → `LOAN_DISB_CNCL` / `DEATH_FORECLOSURE_*`

`reverseTransaction` is called from at least 6 flows: `childLoanReopening`, transaction reversal jobs, manual JE reversal, write-off reversal, refund reversal, and DCF reverse-feed cases.

---

## 8. Idempotency layers (in dependency order)

1. **`client_reference_number` uniqueness** (DB column NOT NULL on `transaction_master`) — enforced by `clientReferenceNumberDedupProcessor` (error 134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1)). **Skipped for `glBalanceZeroisation`** by design.
2. **`reversed` + `reversal_reference_number`** on `transaction_master` — prevents double-reversal (error 134071).
3. **`is_reversible`** flag on `transaction_catalogue` — gates whether a txn type can be reversed at all.
4. **CRR (`client_request_response_log`) status machine** — disbursement-only; not the ledger spine. Detail in `disbursement.md`.
5. **Bank external_ref counter** (`ExternalReferenceNoUtil`) — disbursement-only.

**Known fragility:** several batch flows generate `client_reference_number` from `System.currentTimeMillis()` or `new Date().getTime()` — replays after partial commits get a *new* CREF and bypass the gate at step 1. See `gaps-and-risks.md` time-based CRR rows.

---

## 9. Critical exception code reference

| Code | Meaning | Raised by |
|------|---------|-----------|
| 11008 | Invalid `run_mode` | `validateTransactionDataProcessor` |
| 11012 | Invalid `function_code` | `validateTransactionDataProcessor` |
| 11013 | Invalid `function_sub_code` | `validateTransactionDataProcessor` |
| 130121 | Missing client/transaction reference for reverse | `ReverseTransactionProcessor` |
| 132160 | Currency scaling failure | `validateTransactionDataProcessor` |
| 132161 | Original transaction not found | `ReverseTransactionProcessor` |
| 134065 | Duplicate placeholder in `account_details` | `populateAndValidateAccountDetailsProcessor` |
| 134066 | Insufficient account balance | `validateActorAccountBalanceProcessor` (TRIAL) |
| 134497 (3.3.1.0.1+) / 134067 (3.2.8.4.1) | **Duplicate client_reference_number** | `clientReferenceNumberDedupProcessor` |
| 134071 | Transaction already reversed | `ReverseTransactionProcessor` |
| 134077 | Max balance exceeded | `validateActorAccountBalanceProcessor` |
| 134094 | Reserved amount key collision | `populateAdditionalAmountProcessor` |
| 134252 | Negative or invalid amount | `validateTransactionDataProcessor` |

---

## 10. Java directory tree (`transaction/`)

```
transaction/
├── common/        TransactionConstants (CrDrIndicator: C, D)
├── core/          ComputeEngine, PriceEngine, PriceEngineOld, TaxEngine
│   ├── context/   rule evaluation context
│   ├── pricing/   price computation
│   ├── rules/     rule evaluators
│   └── tax/       tax computation
├── dto/           AccountDTO, AccountingSummaryDTO, ComputeEntryRequest/Response, TransactionCatalogueDetailsDTO, TransactionRuleDTO
├── entity/        7 ledger entities (table 6)
├── manual/        Manual Journal Entry subsystem (DAOs, DTOs, processors, repositories, utility)
├── reverse/processor/ ReverseTransactionProcessor
├── zeroisation/   GL balance zeroisation
├── processor/     34 processor classes (the ones tabulated in §2)
└── repository/    20 DAOs (TransactionMasterDAOService, TransactionDetailsDAOService, TransactionPartitionDetailsDAOService, TransactionMetadataDAOService, TransactionCatalogueDAOService, TransactionRuleDAOService, ProductTransactionCatalogueDAOService …)
```

---

## 11. Test coverage state (high-risk gaps)

Verified by repo grep on this branch:

| Area | `src/test/` hits |
|------|-----------------:|
| `postTransaction` direct unit tests on processors | partial (most processors have a test) |
| `reverseTransaction` integration | **0 hits** |
| `glBalanceZeroisation` | **0 hits** |
| `postManualJournalEntry` / `reverseManualJournalEntry` | **0 hits** |
| `LmsMessageBrokerConsumer` (Kafka disburse path) | **0 hits** |
| Death-foreclosure / DCF insurance writers | **0 hits** |

These match the existing High-risk gap rows; do not assume CI guards them.

---

*Update this file when any processor in §2 is added/removed/reordered, or when a new exception code in §9 is introduced. Keep the verbatim XML block in §2 in sync with the file by line number, not just content.*
