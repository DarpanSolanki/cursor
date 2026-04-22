# Redis / Cache Intelligence (code-verified)

## 1) Tenant-scoped Redis key format
Class: `in.novopay.infra.cache.RedisCacheClient`

Verified: `getTenantSpecificKey(tenantCode, key)` returns:
- `<environmentLowerIfPresent><tenantCode>_<key>`
- where `environmentLowerIfPresent` is `novopay.service.environment` lower-cased, if non-blank.

## 2) Key eviction behavior (IMPORTANT)
Method: `getKeysWithMatchingPrefix(String services)`

Verified: it does not do prefix deletion.
- For each `serviceName` in `services.split("|")`:
  - opens a Redis connection for that service DB index
  - calls `connection.flushDb()`

Implication: any cache invalidation that uses this method can evict unrelated keys stored in the same Redis DB index.

## 3) Disbursement in-flight Redis lock semantics
Code-verified in:
- `in.novopay.los.util.DisburseLoanAPIUtil`
- `in.novopay.accounting.consumers.LmsMessageBrokerConsumer`

Summary:
- Producer sets Redis marker on `<cacheKey>` (no TTL) with value `"in_progress"`.
- Consumer uses a **different** lock key: `"dl" + <originalCacheKey>` (checks + sets it).
- Consumer cleans up both keys in `finally`.

