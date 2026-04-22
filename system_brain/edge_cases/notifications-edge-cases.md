# novopay-platform-notifications — Edge cases (Wave 4)

**Date:** 2026-04-10

- **GAP-058** — `NotificationDAOService#findNotificationMessageByResponseCodeAndLocale`: Redis `set` **without explicit TTL** → stale message text after DB update.
- **OTP** — `OTPDAOService` uses **TTL** from entity/config on `RedisDBConfig.DEFAULT` — verify tenant isolation and brute-force limits in `otp_config`.
- **Kafka consumers** — async SMS/email/FCM; pairing with **GAP-019** (producer swallow) in **other** services when diagnosing “notification never queued”.
