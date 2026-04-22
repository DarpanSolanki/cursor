# novopay-platform-actor — Edge Cases & Risk Scenarios (Wave 3)

**Date**: 2026-04-10  
**Scope:** Full `src/main/java` grep + targeted read on Kafka producers/consumers, portfolio transfer touch points

## Kafka producer — null message key (same pattern as payments GAP-042)

- **File:** `novopay-platform-actor/src/main/java/in/novopay/actor/common/utility/ActorKafkaProducer.java`  
- **Behaviour:** `novopayKafkaProducer.sendMessage(topic, null, message, null)` — no stable partition key for `session_activity_login_`, `geo_tracking_login_logout_audit_`, `update_customer_loan_details_failed`, etc.  
- **Risk:** Ordering not guaranteed per entity; operational diagnosis harder under retry.  
- **Mining:** Not opened as a new GAP number — treat as **duplicate pattern** of GAP-042 / document per-service; fix should be coordinated platform-wide.

## Consumers

- `PosidexInboundActorConsumer`, `SessionActivityLoginConsumer`, `SessionActivityLogoutConsumer`, `UpdateCustomerLoanDetailsConsumer` — standard `NovopayMessageBrokerConsumer` patterns; verify idempotency + error handling per business flow when changing payloads.

## Portfolio transfer

- Large surface in `portfoliotransfer/*` with broad `catch (Exception)` in utilities — review any change with **multi-path state persistence** (actor vs LOS vs accounting); no additional High gap extracted in Wave 3 beyond existing cross-service runbooks.

## Scheduling

- No `@Scheduled` in actor (Wave 3 scan). Cron-driven work for actor is typically invoked from **batch** service.
