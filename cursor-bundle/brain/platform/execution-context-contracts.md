# Execution Context Contract Map — Accounting

**Purpose:** Hidden contracts between processors (`ExecutionContext` / `DefaultExecutionContext`). **Local map is checked before shared map** on `get()` — see `novopay-platform-lib/.../DefaultExecutionContext.java` L146-L151.

**Wave 2 scope:** Full step-by-step EC matrix for all **362** orchestration requests is **not** inlined here; this file adds **verified high-risk rows**, **`postTransaction` spine**, **`loanWriteoff`** (cross-ref **GAP-062**), and **methodology** for extending via grep + XML.

---

## EC Key Registry — Accounting (spine flows)

### `product_transaction_orc.xml` — `postTransaction`

| XML File | Step | Processor | Keys read | Keys written | Set before read? | Type assumed | Null-checked? | Risk |
|----------|------|-----------|-----------|--------------|------------------|--------------|---------------|------|
| product_transaction_orc.xml | 1 | `ValidateTransactionDataProcessor` | `run_mode`, `function_code`, `function_sub_code`, `receipt_number`, `amount` | `field_name` | Request / prior | String / BigDecimal parse | Partial (`getStringValue` blank-safe; `amount` uses `new BigDecimal` only if non-blank) | Low |
| product_transaction_orc.xml | 2 | `PopulateAdditionalInformationProcessor` | `additional_information_details` (JSONArray) | Expands placeholders into shared map; removes `additional_information_details` | Optional | **JSONArray cast** | Only empty-array | **Medium** — `ClassCastException` if wrong type |
| product_transaction_orc.xml | 3 | `PopulateAndValidateAccountDetailsProcessor` | `account_details` | Placeholder codes, `accountNumber` → `AccountDTO`, `is_child_account`, internal account entities | **Must be in request** | **JSONArray cast** | **No** | **High ordering/data** — missing `account_details` → **NPE** at iterator (see **GAP-063**) |
| product_transaction_orc.xml | 4 | `PopulateAdditionalAmountProcessor` | (amount-related keys per implementation) | (derived amount keys) | Varies | — | — | Medium — depends on txn type |
| product_transaction_orc.xml | 5 | `ClientReferenceNumberDedupProcessor` | `client_reference_number`, … | Dedup state | Prior steps | String | Partial | Financial idempotency |
| product_transaction_orc.xml | 6–9 | Catalogue / rules / engines | `transaction_type`, placeholders, … | Rule outputs | Prior + DB | Mixed | Partial | Mis-config catalogue → fatal |

**Cross-service / caller:** Keys such as `tenant_code`, `stan`, `user_id` arrive from **HTTP gateway** + `ExecutionContextPopulator` (not from first processor). Internal **nested** `postTransaction` calls merge parent shared+local into child context (`NovopayInternalAPIClient#doSameServiceCall`).

---

### `loans_orc.xml` — `loanWriteoff` (posting branch)

Documented in `.cursor/accounting-flows.md` **COMPLETE FLOW REGISTRY** and **GAP-062**. Summary:

| Issue | Detail |
|--------|--------|
| **ORDERING / naming** | `prepaymentApproppriationProcessor` reads `total_foreclosure_amount`, `penal_amount`, `foreclosure_date`, `fee_amount`; XML/validator supply `prepayment_amount`, `penalty_amount`, `value_date`, omit `fee_amount`. |
| **Risk** | Null / NPE / wrong appropriation before nested `postTransaction`. |

---

### `loans_orc.xml` — `disburseLoan` (Kafka entry)

| Source | Keys |
|--------|------|
| **Kafka** `LmsMessageBrokerConsumer` | Parses body via `JSONHelperForRequestResponse.parseAPIHeader/parseAPIRequest` into map → `populateExecutionContext`. **No `entity_type`** added for LOS sync result publish. |
| **HTTP** | Same `apiName` when invoked synchronously; validators define mandatory fields. |

---

## Findings taxonomy (Wave 2)

### 1. ORDERING RISK

- **`loanWriteoff`:** Appropriation processor expects keys not yet aligned with upstream XML/validator (**GAP-062**).

### 2. DEAD DATA

- **`PopulateAdditionalInformationProcessor`:** Removes `additional_information_details` after expand — OK. Other flows: grep `executionContext.put("` and cross-check downstream `getValue` per flow (tooling).

### 3. CROSS-SERVICE EC KEYS

- **Inbound HTTP:** Standard headers + request JSON → populator; processors assume gateway contract.
- **Nested internal API:** Child context receives **copy** of parent shared+local at call time (`doSameServiceCall`); keys missing at call boundary surface as callee validation failures or NPEs.

### 4. TYPE ASSUMPTION RISK

- **`PopulateAdditionalInformationProcessor`:** `(JSONArray) executionContext.get("additional_information_details")`.
- **`PopulateAndValidateAccountDetailsProcessor`:** `(JSONArray) executionContext.get("account_details")` without null guard.

### 5. NAMING INCONSISTENCY

- **`penalty_amount`** (write-off validator) vs **`penal_amount`** (`PrepaymentApproppriationProcessor`) vs **`PENAL_DUE_AMOUNT`** (batch/recurring) — same concept, different keys (**GAP-062** / maintenance hazard).

---

## Per-XML coverage status

| XML | Rows in this file | Note |
|-----|-------------------|------|
| product_transaction_orc.xml | `postTransaction` partial | Extend with `reverseTransaction`, `glBalanceZeroisation`, etc. in Wave 3+ |
| loans_orc.xml | `loanWriteoff`, `disburseLoan` pointer | 80+ other requests — automate |
| Remaining 7 XMLs | — | Same methodology |

---

## Related gaps

- **GAP-062** — `loanWriteoff` EC mismatch (High).
- **GAP-063** — `postTransaction` / `PopulateAndValidateAccountDetailsProcessor` NPE on missing `account_details` (Medium).
