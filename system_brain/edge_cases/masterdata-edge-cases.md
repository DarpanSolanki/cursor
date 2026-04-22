# novopay-platform-masterdata-management — Edge cases (Wave 4)

**Date:** 2026-04-10

- **GAP-056** — `GetBulkDatatypeMasterProcessor#getCachedData`: Redis errors return **empty list** (looks like “no master data”).
- **Cache keys** — `{dataType}_{datasubtype}_{locale}` and config `CONFIG_*` keys on `RedisDBConfig.MASTER_DATA`; many `set` calls use **default** TTL — stale data after DB update until eviction.
- **Business date** — batch writer updates Redis config; wrong date propagates to all `job_time` consumers — cross-link accounting/batch runbooks.
