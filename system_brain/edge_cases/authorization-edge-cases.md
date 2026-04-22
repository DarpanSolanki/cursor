# novopay-platform-authorization — Edge cases (Wave 4)

**Date:** 2026-04-10

- **`CheckPermissionProcessor`** — if `usecaseEntity == null`, throws `274002` (**deny**). No “default allow” in this processor.
- **Gateway coupling** — `checkPermissionByUsecase` is **not** invoked when `api_usecase_mapping` row is missing (**GAP-054**); fix at gateway + data, not only authorization service.
- **Redis** — `GetUseCaseDetailsProcessor` caches usecase details by `usecaseNumber` on `RedisDBConfig.AUTHORIZATION` — stale epic/feature metadata possible after DB change.
