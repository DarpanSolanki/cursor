<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.md only routes here. -->

# Bank integration patterns

## JTF template flow

1. **Request**: Processor populates ExecutionContext with required fields → JTF template maps context keys to bank JSON structure → HTTP call via WebClient decorator.
2. **Response**: Raw bank response → `JSONFormatter.parse(template, response)` → flattened `Map<String, Object>` in context.

## Template structure

```json
{
  "class": "SMPL",
  "type": "String",
  "key": "account_number",
  "value": "${account_number}"
}
```

- `SMPL`: Simple key-value mapping from ExecutionContext.
- `CMPLX`: Nested/array structures (MAP type).
- `${key}` references ExecutionContext keys.

## Response parsing gotchas

- `JSONFormatter.parse(...)` flattens nested JSON into a map. Key names depend on template traversal order.
- **Type coercion**: JSON `0` may parse as `Integer 0` or `Double 0.0` depending on the JSON library. Always handle both: `if (value instanceof Number) { ... }`.
- **Nested responses**: Some bank APIs return nested JSON. If template changes, parsed key names change too. Always verify with actual bank response samples.

## WebClient decorator pattern

```java
webClientServiceExecutorDecorator.callBankService(
    executionContext,
    templateName,       // e.g. "neftTransfer"
    requestType,        // POST, PUT
    postProcessor       // optional post-processing
);
```

- Blocking vs async: Some flows use `WebClientServiceExecutorDecorator` (async/reactive), others use blocking REST. Confirm which one the flow uses.
- The response is automatically placed in ExecutionContext via `putAPIResponse()`.

## NEFT flow lifecycle (learned from production)

1. **Initiate**: Create transaction record → `NEFT_STAGE_1_PENDING`.
2. **Stage 1 (NEI)**: Bank validates → success → `NEFT_STAGE_2_PENDING`.
3. **Stage 2 (NEF)**: Bank transfers → success → update `disbursement_status`.
4. **Callback/Inquiry**: Bank confirms final status.

### Critical lessons

- **Lookup both types**: When checking for existing NEFT transactions, include BOTH `DISBURSEMENT_NEFT_NEF` AND `DISBURSEMENT_NEFT_NEI`. Missing one causes duplicate triggers.
- **Update status after each stage**: Set `disbursement_status` to the correct state after NEI and NEF. If not updated, the next trigger re-runs the same stage.
- **Else branch safety**: When a transaction row exists but status is unexpected, set `DO_TRANSACTION = false` to prevent duplicate processing. Don't default to `true`.
- **ReplyCode extraction**: NEFT v2 response is nested differently from v1. Verify the correct JSON path for `replyCode` in the response template.

## Status transition safety

Before any bank call:
1. Check current status — is this call valid in the current state?
2. After the call, update status to the next valid state.
3. On failure, update status to a failure state (not back to the previous state, which could cause retry loops).

## Timeout handling

Bank API calls can timeout without a definitive response. The transaction may have succeeded on the bank side.

- **Never assume failure on timeout**. Instead:
  1. Mark as `INQUIRY_PENDING`.
  2. Run inquiry/callback to get the actual status.
  3. Only then decide success or failure.

---

