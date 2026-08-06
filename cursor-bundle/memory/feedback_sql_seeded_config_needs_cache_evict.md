---
name: feedback-sql-seeded-config-needs-cache-evict
description: A SQL-seeded config value the app reads through @Cacheable is invisible until the Redis key is evicted — the run looks green against the stale value
metadata:
  type: feedback
---

Accounting caches config reads in Redis DB 5 via `@Cacheable(cacheManager = "accountingCacheManager")`.
`AccountInterestDetailsDAOService.findOneByAccountId` is one of them. A fixture that seeds
`account_interest_details.effective_rate` with SQL and then runs a batch job gets the **stale**
rate — the job never sees the seed.

**Why:** the real write path evicts (`save()` carries `@CacheEvict`). SQL-only seeding bypasses that,
and nothing fails loudly — the job completes and writes plausible rows at the old value. On TDPQA-237
the first "red" run accrued at the pre-change 16% and would have been read as proof of the wrong thing.

**How to apply:** when a fixture seeds any column the app reads through a DAO, check that DAO for
`@Cacheable` first. If it is cached, evict before the run:

```bash
redis-cli -n 5 --scan --pattern '<cache_name>::*' | xargs -r redis-cli -n 5 del
```

A service restart is not enough — Redis outlives the JVM. Precedent:
`scripts/dpic/run_dpi_roi_change_e2e.sh`. Related: [[feedback_dpic_harness_gotchas]],
[[feedback_shared_dpi_fixture_needs_teardown]].
