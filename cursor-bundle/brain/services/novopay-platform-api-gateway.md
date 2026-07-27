# `novopay-platform-api-gateway` — Single entry point

> Receives every external request, authenticates the client and session, validates permissions, dedups by STAN, rate-limits, and forwards to the right backend service. Also handles a number of specialised callbacks (Razorpay, CCAvenue, eMandate, eSign, MultiBureau, payments, document).

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.apigateway` |
| DB schema | `mfi_api_gateway` |
| Repo | [`novopay-platform-api-gateway/`](../../novopay-platform-api-gateway/) |
| Service CLAUDE.md | [`trustt-platform-api-gateway/CLAUDE.md`](../../trustt-platform-api-gateway/CLAUDE.md) |

## Routing

**No `<Request>` registry.** Routing is programmatic: `/api/{apiVersion}/{apiName}` → [`GatewayController.java:59`](../../trustt-platform-api-gateway/src/main/java/in/novopay/apigateway/GatewayController.java#L59) → `NovopayAPIClient.callAPI(apiName, version, ...)` → service registry resolves which service owns the apiName via `TenantDetailsDAOService` + `api_usecase_mapping`.

The `NovopayAPIClient` (in `infra-api-client`) is the routing brain.

## Controllers

| Controller | Purpose |
|---|---|
| `GatewayController` | Generic `/api/{v}/{apiName}` proxy |
| `DocumentController` | DMS upload/download |
| `PaymentController` | Payments routes |
| Razorpay/CCAvenue/EMandate/Esign/MultiBureau callback controllers | Inbound webhooks from external providers |
| `RequestForwardController` | Configurable URL forwarding |
| `MfiBankController`, `XMLController` | MFI/XML routes |

## Filter chain

| Filter | What it does |
|---|---|
| `InitialFilter` | Resolves tenant from request → `ThreadLocalContext.setTenant(...)` (context-based, not header-based propagation) |
| `AuthorizationCheckFilter` | `NovopayInternalAPIClient.callInternalAPI("checkPermissionByUsecase", ...)` → throws `NovopayFatalException` on deny |
| `APIRateLimiterFilter` | Bucket4j with in-memory config cache + Redis-backed proxy (`apiRateLimit` DB) |
| `RequestResponseLogFilter`, `MfiRequestResponseLogFilter` | Writes `request_log` / `response_log`, optionally produces to Kafka |

## Kafka

Producer: `producer_id_api_gateway_request_` (and response). Drained by audit service.

Consumer topics (also driven by audit-style flows): `api_gateway_response_*`, `api_gateway_request_*`, `telemetry_perf_log_*`.

## DB clusters

| Cluster | Tables |
|---|---|
| Sessions | `session` (token → user details, expiry) |
| Clients | `client`, `client_key` (code, key type, version, rotation) |
| Routing / authz mapping | `api_usecase_mapping` (apiName → usecase) |
| Dedup | `request_stan_log` |
| Audit | `request_log`, `response_log` |
| Forwarding config | `request_forward` |
| Callbacks | `CallbackRequestResponseLogEntity` |

## Concepts

- **STAN** — System Trace Audit Number; per-request unique. Used for dedup, replay, idempotent retry. Rejected if seen recently in `request_stan_log`.
- **Tenant** — resolved from request (host, header, or path) and stored in `ThreadLocalContext` for downstream propagation. `NovopayInternalAPIClient` reads ThreadLocal when posting to backends.
- **Usecase mapping** — `api_usecase_mapping.apiName` → usecase code → permission check.
- **Rate limit** — Bucket4j buckets sized per `api_usecase_mapping` config or env override; backed by Redis for cross-instance share.

## Known gotchas

1. **Routing is not data-driven via XML** — adding a new Request anywhere requires the `api_usecase_mapping` row + tenant service registry update.
2. **Tenant propagation is context-based** — broken `InitialFilter` = mis-tenant routing.
3. **Callbacks have their own controllers** — don't try to route external webhooks through `GatewayController`.
4. **STAN dedup is gateway-side** — same payload from different STANs goes through; it's the caller's job to keep STAN deterministic for retries.
