# novopay-platform-api-gateway — Edge cases (Wave 4)

**Date:** 2026-04-10

- **GAP-054** — Missing `api_usecase_mapping` row ⇒ **no** `checkPermissionByUsecase` call (**default-allow** for that apiName/function tuple).
- **GAP-055** — `/forward/*` **not** covered by `/api/*` or `/mfi/*` servlet filters ⇒ bypass session, client auth, STAN dedupe, rate limit, permission filter; **INFO logs** include full forwarded body.
- **MFI path** — `MfiInitialFilter` allowlist (`mfiAllowedApiList`); mis-config ⇒ blanket333 errors or overexposure.
- **Dual STAN dedupe** — Redis vs `request_stan_log` (DB) mode — ensure env consistency.
- **Scheduler** — `FilterConfig#sessionPurge` cron clears expired sessions per tenant (see `.cursor/scheduler-registry.md`).
