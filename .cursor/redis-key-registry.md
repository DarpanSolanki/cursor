# Redis key registry — all waves (consolidated)

**Purpose:** Single index of **observed** Redis usage across services mined in Waves 1–4. Keys are typically **tenant-prefixed** by `ICacheClient` / `NovopayCacheClient` (exact prefix behaviour is infra implementation–dependent).

**Legend — TTL:** **Y** = explicit TTL in code path; **Default** = `set` overload without TTL (platform default expiry from cache config); **N** = no expiry set in code (key persists until manual delete / server eviction).

**Risk:** Summarises operational/security impact, not a duplicate of `.cursor/gaps-and-risks.md` (e.g. stale lock keys, `flushDb`, forward path).

---

## novopay-platform-api-gateway

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `stan` (duplicate request) | Y | `novopay.service.gateway.long.stan.ttl.millisecond` (e.g. 600000 ms) | Dedupe STAN in Redis mode | **Medium** — mis-config ⇒ duplicate or false rejects |
| Session token → user DTO | Y | session timeout (sec × 1000) | Session cache | **High** if TTL/DB diverge |
| `session_expiry_<userId>` | Y | same as session | Active session marker | **Medium** |
| `client_key_<clientCode>_<keyType>_<keyVersion>` | N | — | Client key entity cache | **Medium** — stale keys after rotation (see gateway CLAUDE) |
| `client_<clientCode>` | N | — | Client entity cache | **Medium** — not cleared on key rotation |
| `req_forward_<requestName>` | N | — | Cached forward URL | **High** — stale URL + pairs with `GAP-055` trust boundary |
| `superset_user_session_token_*`, `superset_user_id_*` | Y | guest/session aligned | Superset guest token mapping | **Medium** |
| Rate limiting (Bucket4j) | Y / varies | `redisApiRateLimitTemplate` + proxy config | API throttling | **Low** — availability |

*Source:* `novopay-platform-api-gateway/CLAUDE.md`, `APIRateLimiterFilter`, `SessionDAOService`, `RequestForwardProcessor#urlFinder`.

---

## novopay-platform-accounting-v2

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| Disburse consumer `dl` / in-flight key | N | — | Kafka consumer dedupe | **High** — see gaps table (stale lock) |
| Various product/config caches | Default / Y | per call site | Masterdata-driven config | **Medium** |

*Source:* `LmsMessageBrokerConsumer`, gaps table; deep per-job keys omitted here — use service + `accounting-edge-cases.md`.

---

## novopay-mfi-los

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| Disburse in-flight (`DisburseLoanAPIUtil`) | N | — | Async disburse dedupe | **High** — gaps table |

---

## novopay-platform-payments

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| (service-specific) | — | — | Collections / settlement caches via infra | **Low–Medium** — verify call sites when changing money paths |

*Wave 4 note:* no dedicated Redis key file in repo root; payments uses infra cache in multiple DAOs — extend this table when touching those paths.

---

## novopay-platform-batch

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `current.business.date` (masterdata key) | — | Removed then re-read | Business date for job_time | **Medium** — cross-tenant if `ThreadLocalContext` wrong (GAP-049) |

*Source:* `SchedulerCommonService#setJobTime`.

---

## novopay-platform-task / novopay-platform-actor

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `USER_DETAILS*`, `EMPLOYEE_DETAILS*`, `OFFICE_DETAILS*`, etc. | Default | infra default | Actor hierarchy cache (task) | **Medium** — stale assignment |
| Actor `client_*`, notification caches | per actor CLAUDE | — | CRM / notification | **Medium** |

---

## novopay-platform-masterdata-management

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `<dataType>_<datasubtype>_<locale>` (+ optional `_<code>`) | Default | `cacheClient.set` without TTL in bulk processors | Code master cache | **Medium** — stale dropdowns; **GAP-056** empty list on Redis error |
| `CONFIG_<propKey>` (`ConfigValue` prefix) | Default / updated on write | configuration processors | Tunable config | **High** if wrong business date / limits |

*DB index:* `RedisDBConfig.MASTER_DATA`.

---

## novopay-platform-authorization

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `<usecaseNumber>` (use case detail DTO) | Default | `GetUseCaseDetailsProcessor` | Usecase metadata cache | **Medium** — stale permissions until refresh |

*DB index:* `RedisDBConfig.AUTHORIZATION`.

---

## novopay-platform-notifications

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| `<responseCode>_<locale>` | Default | `NotificationDAOService` `set` without TTL | Message text cache | **Medium** — **GAP-058** stale templates |
| OTP keys (`otpEntity.getKey()`, generic `key`) | Y | `otpEntity.getTtl()` / param | OTP store | **High** — auth bypass if TTL/attempt logic wrong |

*DB index:* `NOTIFICATION`, `DEFAULT` (OTP).

---

## novopay-platform-approval

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| Product/config via `NovopayCacheClient` | Default | processor-dependent | Maker-checker config | **Medium** |

---

## novopay-platform-audit

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| — | — | — | **No Redis** in audit service | — |

---

## novopay-platform-dms

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| — | — | — | **No Redis** in DMS Java grep (Wave 4) | — |

---

## novopay-platform-lib (infra-cache)

| Key pattern (logical) | TTL | TTL value / notes | Purpose | Risk |
|----------------------|-----|-------------------|---------|------|
| (entire DB index) | — | `flushDb()` | Administrative wipe | **Critical** — gaps table `RedisCacheClient` |

---

## Maintenance

When adding Redis usage: update this file **and** the service `CLAUDE.md` / edge-case note. For **exact** TTL milliseconds, read `NovopayCacheClient` / env defaults for the deployment.
