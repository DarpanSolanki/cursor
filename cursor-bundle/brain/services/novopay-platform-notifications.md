# `novopay-platform-notifications` — Multi-channel notification hub

> SMS, email, FCM push, in-app, OTP. Template-driven; service-specific codes (e.g. `LOS-5095`) are mapped to canonical notification codes (`LOAN_APPROVED_SMS`). Async via Kafka consumers; **no producer** of its own.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.notifications` |
| DB schema | `mfi_notifications` |
| Repo | [`novopay-platform-notifications/`](../../novopay-platform-notifications/) |
| Service CLAUDE.md | [`trustt-platform-notifications/CLAUDE.md`](../../trustt-platform-notifications/CLAUDE.md) |

## API surface — `ServiceOrchestrationXML.xml` (~13 Requests)

`getMessage`, `getResponseCodeByUsecaseAndSubusecase`, `getNotificationMessageByNotificationCode`, `sendSMS`, `sendEmail`, `sendFCMNotification`, `getFCMTokens`, `updateFCMTokenForUser`, `updateNotificationLog`.

Used heavily by accounting at the end of every interactive Request — `accounting_getNotificationMessage` resolves the user-facing copy for the response code + use-case story.

## Kafka — consumer-only (no producer)

| Topic prefix | Purpose |
|---|---|
| `async_notifications_` | Generic async notification dispatch |
| `alerts` | Internal alerts |
| `notification_sms_` | SMS channel |
| `notification_email_` | Email channel |
| `notification_fcm_` | FCM push channel |

## Outbound

- **FCM gateway** — `https://fcm.googleapis.com/fcm/send` ([`CustomFCMService.java`](../../trustt-platform-notifications/src/main/java/in/novopay/notifications/fcm/service/CustomFCMService.java))
- **SMS gateways** — Vodafone XML POST via Apache `HttpClient` ([`SmsGatewayImplVFLowPriority.java`](../../trustt-platform-notifications/src/main/java/in/novopay/notifications/sms/adapter/vf/SmsGatewayImplVFLowPriority.java))
- Other SMS/email providers via similar adapter pattern

## Inbound

Everyone: LOS (consent OTP, loan alerts), actor (password reset), accounting (payment due, response copy), payments (collection receipts, PTP reminders), task (escalation), approval (decision notifications), consents (OTP).

## Concepts

- **Notification code** — unique key in `notification_message` (e.g. `LOAN_APPROVED_SMS`, `PAYMENT_DUE_EMAIL`). Stores per-locale templates.
- **Code mapping** — `code__notification_code__mapping` table maps `(serviceName, code)` → canonical notification code. Lets services use service-local codes (e.g. `LOS-5095`) and have templates change without code-change.
- **Template substitution** — placeholders resolved per request from incoming payload.
- **Channel routing** — three orchestration Requests + Kafka topic prefixes per channel; FCM path triggered by `function_code = "FCM"`.
- **OTP** — generated/validated entirely in **Redis (DEFAULT, DB 0)** — no DB row. Config-driven expiry + attempt thresholds in `otp_config` per tenant.

## Caching

Redis DB index **2 (NOTIFICATION)** for message templates. DB 0 for OTP.

## Known gotchas

1. **Multi-channel consistency** requires matching `code__notification_code__mapping` rows for each channel.
2. **OTP lives only in Redis** — TTL is critical; Redis flush blanks all in-flight OTPs.
3. **Consumer-only** — lag affects async delivery; no recovery once a Kafka message is dropped without DLQ handling.
