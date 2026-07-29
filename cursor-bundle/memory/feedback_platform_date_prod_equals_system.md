# PlatformDateUtil — prod valueDate == systemDate

**Standing:** Do **not** invent a separate `system_created_on` (or dual-clock stamp) for “latest” money rows to fix QA business-date skew.

Evidence (`trustt-platform-lib/.../PlatformDateUtil.java`):
- `getValueDateInLong()` → if `server.environment == "test"` → testing mix of `current.business.date` + wall clock
- else → `getTransactionDateInLongForProduction()` → **`getSystemDateInLong()` only**

`SetCommonAttributesProcessor` sets `ATTR_VALUE_DATE` from `getValueDateInLong()`.

**TDPQA-207:** QA can stamp `prepayment_details.created_on` from a **future** business date; prod cannot via this util. Correct product fix = demote REJECTED in BY_LATEST ORDER BY (L1), not a new column.

KG: `diag:platform.platform_date_prod_equals_system` + `diag:ordering.by_latest_rejected_business_date`.
