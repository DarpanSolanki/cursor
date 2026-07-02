---
description: "ExecutionContext discipline — the #1 source of runtime bugs; key management, null safety, scope control"
globs:
  - "**/*.java"
  - "**/*.xml"
alwaysApply: false
---

# ExecutionContext discipline

ExecutionContext is the central contract between processors. It is stringly-typed, mutable, and shared — making it the #1 source of subtle runtime bugs.

## Reading values safely

```java
// Always validate before use
String accountNumber = executionContext.getStringValue("account_number");
if (StringUtils.isBlank(accountNumber)) {
    throw new NovopayFatalException("132247");
}

Long accountId = executionContext.getLongValue("account_id");
if (accountId == null) {
    throw new NovopayFatalException("132248");
}

// For typed objects
LoanAccountEntity entity = executionContext.getValue("loan_account_entity", LoanAccountEntity.class);
if (entity == null) {
    throw new NovopayFatalException("134139");
}
```

## put() vs putLocal()

- `put(key, value)` — visible to ALL downstream processors in the orchestration flow. Use for data that the next processor needs.
- `putLocal(key, value)` — scoped to the current processor/API call. Does NOT propagate. Use for:
  - API request parameters that should not leak
  - Temporary computation results
  - Bank call request fields

**Rule**: Default to `putLocal()`. Only use `put()` when a downstream processor explicitly needs the key.

## Avoid accidental overwrites

- Before `put(key, value)`, check if the key is already set and whether overwriting is intended.
- Common trap: setting `account_number` in one processor, then a downstream processor reads a different `account_number` from a nested API call that overwrote it.
- If populating derived keys (e.g. parsed response fields), set them only when missing/blank.

## Key naming

- Use snake_case consistently: `account_number`, `product_scheme_id`, `office_id`.
- Use constants for frequently-used keys (e.g. `AccountingConstants.ACCOUNT_NUMBER`).
- For flow-specific keys, prefix with flow name if ambiguous (e.g. `disbursement_status` vs `collection_status`).

## Common keys across flows

| Key | Type | Usage |
|-----|------|-------|
| `account_number` | String | Loan account number |
| `account_id` | Long | Loan account PK |
| `external_ref_number` | String | External reference (LOS) |
| `product_scheme_id` | Long | Product/scheme |
| `office_id` / `office_code` | Long/String | Branch |
| `partner_code` | String | Bank partner selection |
| `performed_by` | Long | Audit: who performed |
| `performed_on` | Date | Audit: when |
| `function_code` | String | Operation type (DEFAULT, APPROVE) |
| `function_sub_code` | String | Sub-operation (CREATE, UPDATE) |

## Debugging ExecutionContext issues

When a key is unexpectedly null or wrong:
1. Check orchestration XML — is the key set by a validator, API call, or upstream processor?
2. Check if a `<Control>` branch skipped the processor that sets the key.
3. Check if an inter-service API call overwrote the key via `putAPIResponse()`.
4. Check if the consumer populates context differently from the API entry point.
