---
description: "API contract safety — backward compatibility, additive changes, response semantics, cross-module impact"
globs:
  - "**/*.java"
  - "**/*.xml"
alwaysApply: false
---

# API contract safety

## The iron rule

**Existing callers must work unchanged after any API change.** This is the single most important rule for a multi-module fintech platform where accounting, LOS, payments, batches, and webapp all call each other.

## What counts as a contract

- API response JSON shape (field names, types, nullability, array vs object)
- API request parameters (required vs optional, types)
- Error codes and their meaning
- ExecutionContext keys written by processors (downstream processors depend on them)
- Kafka message format
- Kafka/async event payload fields that downstream services treat as mandatory keys (missing fields can cause silent no-op).
- Shared library method signatures

## Additive changes only

```java
// SAFE: Adding a new field (old callers ignore it)
response.put("charges_details", chargesList);
response.put("charges_configured", !chargesList.isEmpty()); // NEW — additive

// UNSAFE: Changing existing semantics
// Before: charges_details was never empty (had placeholder when no config)
// After: charges_details is empty when no config
// → Breaks LOS KFS which does charges_details.get(0)
```

## Checklist before changing any API/response

1. **Find all callers**: grep across accounting, LOS, actor, payments, task, batch, webapp, reporting for the API name, response keys, and shared method.
2. **Understand their assumptions**: Does the caller assume the list is non-empty? Does it assume a field is never null? Does it check `.size() > 0` before iterating?
3. **Test both paths**: With and without data. Old callers with old behavior, new callers with new behavior.
4. **Add, don't change**: New fields are safe. Changing the meaning of existing fields is breaking.
5. **Separate flags for semantics**: If a list can now be empty when it wasn't before, add a boolean flag (e.g. `charges_configured`) so callers can distinguish "no data configured" from "data is empty array".

## Cross-module impact map

| Changed module | Check these callers |
|---------------|-------------------|
| Accounting API | LOS (AccountingUtil), Payments, Batches, Webapp |
| LOS API | Accounting, Actor, Webapp |
| Actor API | LOS, Accounting, Payments, Webapp |
| Payments API | Accounting, LOS, Webapp |
| Shared lib | ALL modules that depend on it |

## When in doubt

Treat it as breaking. List all callers, describe the change, and get review before merging.
