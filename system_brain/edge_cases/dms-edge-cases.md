# novopay-platform-dms — Edge cases (Wave 4)

**Date:** 2026-04-10

- **Redis** — no `ICacheClient` usage found under `src/main/java` in Wave 4 scan (document storage / DB–centric).
- **Timeouts** — connection/socket timeout constants exist (`NovopayDocumentCommonConstants`); verify all HTTP client call sites use them (avoid unbounded hangs).
- **Gateway path** — document upload/download routes go through gateway `DocumentValidationFilter` for configured APIs; bypass paths must not widen without review.
