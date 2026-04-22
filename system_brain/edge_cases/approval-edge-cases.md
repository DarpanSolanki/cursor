# novopay-platform-approval — Edge cases (Wave 4)

**Date:** 2026-04-10

- **Target API execution** — `target_api_name` drives post-approve calls to actor/accounting/LOS/task; misconfiguration ⇒ wrong downstream action (existing CLAUDE gotcha).
- **Redis** — processors inject `NovopayCacheClient` for product/config reads; behaviour depends on infra default TTL (extend `redis-key-registry.md` when changing paths).
- **AuthZ** — relies on gateway + authorization for interactive flows; internal-only callers must still enforce usecase checks.
