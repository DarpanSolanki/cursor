---
description: Deep framework awareness — orchestration engine, ExecutionContext, transactions, partner discovery, templates, infra-navigation internals
alwaysApply: true
---

# Novopay framework deep awareness

## Orchestration engine (infra-navigation)

- Flow defined in `deploy/application/orchestration/*.xml`. Validators → Processors → API calls → Controls.
- `ServiceOrchestrator.executeProcessors()` runs the flow. Consumers can trigger full orchestration or call services directly.
- Branching: `<Control method="regExp" pattern="${function_sub_code}" condition="=" value="CREATE">` for flow routing.
- Maker-checker: `maker_checker_enabled` flag controls approval vs direct execution path.

## Transaction boundaries (critical)

- **Implicit** (POST/PUT/DELETE): Single transaction; commit only if all processors succeed. Rollback on any fatal exception.
- **Explicit** (GET, internal API calls): Commit per processor/step. Each step is independent.
- **Nested `<Transaction>` blocks**: For independent commits within a single API (e.g. portfolio transfer uses `explicitTxnMgmt="true"`).
- **Inter-service calls**: Each microservice call = separate transaction. If MS A calls MS B, MS B's commit is independent. Design for partial failure.
- **Same-JVM internal API**: Still uses separate transaction boundary (explicit management). Not a shared transaction.
- **Fatal exception**: Immediate rollback of current transaction. No undo processors run first.
- **Non-fatal exception**: Undo processors run (if defined), then rethrow.
- **Never use @Transactional in services** unless framework explicitly requires it (rare: `REQUIRES_NEW` for filler updates).

## ExecutionContext internals

- Interface: `in.novopay.infra.platform.navigation.ExecutionContext`.
- `put(key, value)` — shared across all downstream processors in the flow.
- `putLocal(key, value)` — scoped to current step; does not propagate. Use for API call params that must not leak.
- `getStringValue(key)` — returns String, null if absent.
- `getLongValue(key)` — returns Long, null if absent. 
- `getValue(key, Class)` — typed extraction.
- `getBooleanValue(key)`, `getIntegerValue(key)`, `getDecimalValue(key)` — typed shortcuts.
- `getAPIRequestJson()` / `getAPIResponse()` / `putAPIResponse()` / `getValueFromAPIResponse(responseName, key, Class)` — for inter-service and bank API results.
- **Danger**: Keys are stringly-typed. Typos compile but fail at runtime. Always verify key names against orchestration XML and upstream processors.

## Partner discovery + bean routing

- `AbstractPartnerDiscoveryService` reads `executionContext["partner_code"]` to select bank-specific implementation.
- Different methods may route to different implementations (e.g. blocking REST vs WebClient decorator). Confirm the exact method invoked in the flow.
- Bank implementations: `NeftServiceHdfc`, `CustomerServiceHdfc`, `MiscFundTransferDecorator`, etc.

## Bank integration templates (JTF)

- Templates: `deploy/application/templates/bankIntegrationRequest/{partner}/` and `bankIntegrationResponse/{partner}/`.
- JSON structure: `class: "SMPL"` or `"CMPLX"`, `type: "String"` or `"MAP"`. Maps ExecutionContext keys to bank request fields.
- `JSONFormatter.parse(...)` flattens bank response into a map. Key names depend on template traversal — changes to template shape change parsed keys.
- **Type gotcha**: JSON numbers may parse as `0` (int) or `0.0` (double) depending on the JSON library. Always handle both.
- WebClient decorator flows may differ in timing/return contracts from blocking flows. Validate sync vs async semantics.

## Infra-platform validators

- `mandatoryFieldValidator` / `stringMandatoryFieldValidator` — required field check.
- `patternFieldValidator` — regex validation.
- `numberValidator` / `numberRangeValidator` — numeric range.
- `stringLengthValidator`, `emailValidator`, `mobileNoValidator`, `datePatternValidator`.
- `masterDataValidator` — validates against master data cache.
- Used in orchestration XML: `<Validator bean="mandatoryFieldValidator"><IParam fieldName="account_number" errorCode="132001"/></Validator>`.

## Mandatory verification for any change

- Read the orchestration XML for the affected flow.
- Trace all downstream processors that read keys you modify.
- Verify status transitions, failure flags, persistence logic across retry/callback/inquiry paths.
- Check if consumers (Kafka) trigger the same flow — they may populate context differently.