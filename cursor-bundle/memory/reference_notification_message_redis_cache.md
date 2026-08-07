---
name: notification-message-redis-cache
description: Changing a notification_message row does not take effect until the Redis key <tenant>_<code>_<locale> in db 2 is evicted
metadata:
  type: reference
---

Changing a notification_message row does not take effect until the Redis key <tenant>_<code>_<locale> in db 2 is evicted

**Why:** TDPQA-241, 2026-08-07. Reworded LON-DSB-011, updated the DB row, restarted accounting — and the API still returned the old text. `NotificationUtil.getResponseMessage` reads `cacheClient.get(tenant, responseCode + '_' + locale, RedisDBConfig.NOTIFICATION)` first and only falls back to the getMessage internal API on a miss. The cache lives in Redis db **2**, so a service restart does not clear it.

**How to apply:** after any notification_message change, `redis-cli -n 2 --scan --pattern '*<code>*'` then `del` the key — e.g. `localmfi_134498_en-in`. Do the same before believing a message-text test result; a green run against a stale key proves nothing. If QA reports the old wording after a build, this key is the first thing to check, not the migration. Redis db map: `RedisDBConfig` (NOTIFICATION=2, ACCOUNTING=5).
