# novopay-platform-lib — Wave 1 edge cases (mining)

**Date:** 2026-04-10  
**Scope:** `src/main/java` — lens-oriented scan (exception paths, Redis, HTTP/Kafka, security, async).  
**Related:** `.cursor/gaps-and-risks.md` GAP-018..020 (pre-existing), **GAP-031..034** (this wave).

---

## Edge case: Non-TTL Redis `set` primitive

- **Trigger:** Any caller uses `ICacheClient#set(tenant, key, value, dbIndex)` without the TTL overload.
- **Current behavior:** Key persists with no expiry until explicit delete or operational flush.
- **Expected behavior:** Default or mandatory TTL for cache semantics; explicit exceptions documented.
- **Gap reference:** GAP-031
- **File:** `infra-cache/.../RedisCacheClient.java`

## Edge case: Paytm remittance logs live bearer token and response body

- **Trigger:** Any Paytm remittance / status call through `PaytmApiClient#invokeApi`.
- **Current behavior:** INFO logs include `Authorization` token and raw API response string.
- **Expected behavior:** No secrets or full payloads in logs; correlation id + outcome only.
- **Gap reference:** GAP-032
- **File:** `infra-transaction-paytm/.../PaytmApiClient.java`

## Edge case: `HttpClientUtil` logs keystore password and uses permissive TLS

- **Trigger:** `enableHttpsTunnelWithCertificate` used for HTTPS client construction.
- **Current behavior:** Password concatenated into INFO log line; `NoopHostnameVerifier` + trust loaded from supplied keystore.
- **Expected behavior:** No password logging; production-grade trust + hostname verification unless explicitly dev-only.
- **Gap reference:** GAP-033
- **File:** `infra-transaction-interface/.../HttpClientUtil.java`

## Edge case: Same-service internal API failure prints full request JSON

- **Trigger:** `NovopayInternalAPIClient#doSameServiceCall` and nested orchestration returns `status=FAIL`.
- **Current behavior:** INFO log includes full `requestString` (formatted API body).
- **Expected behavior:** Redacted failure context (apiName, code, stan, tenant).
- **Gap reference:** GAP-034
- **File:** `infra-navigation/.../NovopayInternalAPIClient.java`

## Edge case: Kafka producer send swallow (framework)

- **Trigger:** `NovopayKafkaProducer#sendMessage` throws before/around `producer.send`.
- **Current behavior:** Exception caught, logged, no propagation to caller.
- **Expected behavior:** Fail-fast or outbox for money-critical topics.
- **Gap reference:** GAP-019 (pre-existing; not re-numbered)
- **File:** `infra-message-broker/.../NovopayKafkaProducer.java`

## Edge case: Async orchestration fire-and-forget

- **Trigger:** `ServiceOrchestrator#processAsyncRequest`.
- **Current behavior:** `CompletableFuture.runAsync` with no completion handler or durable job record.
- **Expected behavior:** Durable async status + failure surfacing.
- **Gap reference:** GAP-020 (pre-existing)
- **File:** `infra-navigation/.../ServiceOrchestrator.java`

## Edge case: Crypto helper empty catch + hardcoded key

- **Trigger:** HMAC / encryption helpers in `EncryptionUtil`.
- **Current behavior:** Empty catch returns trimmed empty hash; separate path uses hardcoded AES key string.
- **Expected behavior:** Fail-fast crypto; secrets from vault.
- **Gap reference:** GAP-018 (pre-existing)
- **File:** `infra-transaction-interface/.../EncryptionUtil.java`

## Edge case: `flushDb` helper on Redis connection

- **Trigger:** `RedisCacheClient#getKeysWithMatchingPrefix` used operationally.
- **Current behavior:** Iterates services and calls `connection.flushDb()` per connection.
- **Expected behavior:** Highly restricted admin-only tooling; never callable from hot paths.
- **Gap reference:** Table row *Broad Redis flushDb()* in `.cursor/gaps-and-risks.md`
- **File:** `infra-cache/.../RedisCacheClient.java`
