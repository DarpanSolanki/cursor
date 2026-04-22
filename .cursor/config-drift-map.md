# Config drift map (rebuilt)

**Scope:** `**/src/main/resources/application.properties` in sliProd (no `application.yml` at service roots). **Date:** 2026-04-10. **Plus:** `deploy/application/messagebroker/MessageBroker.xml` consumer threads/poll; sample hardcoded URLs.

## 1) Timeout, TTL, duration-like properties — cross-service matrix

Empty cell = property **absent** in that service file.

| Property | novopay-mfi-los | novopay-platform-accounting-v2 | novopay-platform-actor | novopay-platform-api-gateway | novopay-platform-approval | novopay-platform-audit | novopay-platform-authorization | novopay-platform-batch | novopay-platform-dms | novopay-platform-lib | novopay-platform-masterdata-management | novopay-platform-notifications | novopay-platform-payments | novopay-platform-simulators | novopay-platform-task | trustt-platform-reporting |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| idfc.imps.service.connection.timeout |  |  |  |  |  |  |  |  |  |  |  |  | 10000 |  |  |  |
| idfc.imps.service.socket.timeout |  |  |  |  |  |  |  |  |  |  |  |  | 120000 |  |  |  |
| novopay.internal.api.socket.timeout |  |  |  | 10000 |  |  |  |  |  |  |  |  |  |  |  |  |
| novopay.service.gateway.duration.in.seconds |  |  |  | 60 |  |  |  |  |  |  |  |  |  |  |  |  |
| novopay.service.gateway.long.session.timeout.sec |  |  |  | 2592000 |  |  |  |  |  |  |  |  |  |  |  |  |
| novopay.service.gateway.long.stan.ttl.millisecond |  |  |  | 600000 |  |  |  |  |  |  |  |  |  |  |  |  |
| novopay.service.gateway.session.timeout.sec |  |  |  | 900 |  |  |  |  |  |  |  |  |  |  |  |  |
| spring.mail.properties.mail.smtp.connectiontimeout |  |  |  |  |  |  |  |  |  |  |  | 5000 |  |  |  |  |
| spring.mail.properties.mail.smtp.starttls.enable |  |  |  |  |  |  |  |  |  |  |  | true |  |  |  |  |
| spring.mail.properties.mail.smtp.timeout |  |  |  |  |  |  |  |  |  |  |  | 5000 |  |  |  |  |
| spring.mail.properties.mail.smtp.writetimeout |  |  |  |  |  |  |  |  |  |  |  | 5000 |  |  |  |  |

## 2) Kafka — `spring.kafka` / bootstrap (application.properties)

| Service | spring.kafka.bootstrap-servers | message.broker.bootstrap.servers |

|---------|-------------------------------|-----------------------------------|

| novopay-mfi-los |  | http://127.0.0.1:9092 |
| novopay-platform-accounting-v2 | ${message.broker.bootstrap.servers} | http://127.0.0.1:9092 |
| novopay-platform-actor |  | http://localhost:9092 |
| novopay-platform-api-gateway | ${message.broker.bootstrap.servers} | http://127.0.0.1:9092 |
| novopay-platform-approval |  | http://127.0.0.1:9092 |
| novopay-platform-audit |  | http://127.0.0.1:9092 |
| novopay-platform-authorization |  | http://127.0.0.1:9092 |
| novopay-platform-batch |  |  |
| novopay-platform-dms |  | http://127.0.0.1:9092 |
| novopay-platform-lib |  |  |
| novopay-platform-masterdata-management |  | http://127.0.0.1:9092 |
| novopay-platform-notifications |  | http://127.0.0.1:9092 |
| novopay-platform-payments |  | http://127.0.0.1:9092 |
| novopay-platform-simulators |  |  |
| novopay-platform-task |  | http://127.0.0.1:9092 |
| trustt-platform-reporting |  | http://127.0.0.1:9092 |

## 3) Kafka consumer runtime — from `MessageBroker.xml` (per consumer)

**Note:** `session.timeout.ms` / `max.poll.interval.ms` are **not** set per consumer in XML in this repo; they use **Spring Kafka / broker defaults** unless overridden in code or global `spring.kafka.consumer.*` (largely **absent** in scanned `application.properties`). Below is what **is** explicit.

| Service | topicPrefix | pollTime ms | numberOfThreads | maxPollRecords | consumersGroupIdPrefix |

|---------|-------------|------------|-----------------|----------------|-------------------------|

| mfi-los | geo_tracking_audit_ | 2000 | 2 | 2 | geo_tracking_audit_ |
| mfi-los | geo_tracking_login_logout_audit_ | 3000 | 2 | 1 | geo_tracking_login_logout_audit_ |
| mfi-los | posidex_los_inbound_ | 3000 | 1 | (unset) | posidex_inbound_los_consumer |
| mfi-los | posidex_los_outbound_ | 3000 | 1 | (unset) | posidex_outbound_los_consumer |
| mfi-los | indl_qde_borrower_onboarding_factiva_service_ | 3000 | 1 | 1 | indl_qde_borrower_onboarding_factiva_ |
| mfi-los | indl_qde_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | indl_qde_borrower_default_factiva_retry_ |
| mfi-los | indl_qde_borrower_qde_factiva_service_retry_ | 3000 | 1 | 1 | indl_qde_borrower_qde_factiva_retry_ |
| mfi-los | indl_qde_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_qde_borrower_default_internal_dedupe_retry_ |
| mfi-los | indl_qde_borrower_qde_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_qde_borrower_qde_internal_dedupe_retry_ |
| mfi-los | indl_qde_borrower_onboarding_posidex_service_ | 5000 | 1 | 1 | indl_qde_borrower_onboarding_posidex_ |
| mfi-los | indl_qde_borrower_onboarding_posidex_service_second_call_ | 6000 | 1 | 1 | indl_qde_borrower_onboarding_posidex_second_call_ |
| mfi-los | indl_qde_borrower_onboarding_multi_bureau_service_ | 6000 | 1 | 1 | indl_qde_borrower_onboarding_multi_bureau_ |
| mfi-los | indl_qde_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | indl_qde_borrower_default_posidex_retry_ |
| mfi-los | indl_qde_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_qde_borrower_default_posidex_second_call_retry_ |
| mfi-los | indl_qde_borrower_qde_posidex_service_retry_ | 5000 | 1 | 1 | indl_qde_borrower_qde_posidex_retry_ |
| mfi-los | indl_qde_borrower_qde_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_qde_borrower_qde_posidex_second_call_retry_ |
| mfi-los | indl_qde_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_qde_borrower_default_multi_bureau_retry_ |
| mfi-los | indl_qde_borrower_qde_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_qde_borrower_qde_multi_bureau_retry_ |
| mfi-los | indl_qde_co_borrower_onboarding_factiva_service_ | 3000 | 1 | 1 | indl_qde_co_borrower_onboarding_factiva_ |
| mfi-los | indl_qde_co_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | indl_qde_co_borrower_default_factiva_retry_ |
| mfi-los | indl_qde_co_borrower_qde_factiva_service_retry_ | 3000 | 1 | 1 | indl_qde_co_borrower_qde_factiva_retry_ |
| mfi-los | indl_qde_co_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_qde_co_borrower_default_internal_dedupe_retry_ |
| mfi-los | indl_qde_co_borrower_qde_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_qde_co_borrower_qde_internal_dedupe_retry_ |
| mfi-los | indl_qde_co_borrower_onboarding_posidex_service_ | 5000 | 1 | 1 | indl_qde_co_borrower_onboarding_posidex_ |
| mfi-los | indl_qde_co_borrower_onboarding_posidex_service_second_call_ | 6000 | 1 | 1 | indl_qde_co_borrower_onboarding_posidex_second_call_ |
| mfi-los | indl_qde_co_borrower_onboarding_multi_bureau_service_ | 6000 | 1 | 1 | indl_qde_co_borrower_onboarding_multi_bureau_ |
| mfi-los | indl_qde_co_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | indl_qde_co_borrower_default_posidex_retry_ |
| mfi-los | indl_qde_co_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_qde_co_borrower_default_posidex_second_call_retry_ |
| mfi-los | indl_qde_co_borrower_qde_posidex_service_retry_ | 5000 | 1 | 1 | indl_qde_co_borrower_qde_posidex_retry_ |
| mfi-los | indl_qde_co_borrower_qde_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_qde_co_borrower_qde_posidex_second_call_retry_ |
| mfi-los | indl_qde_co_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_qde_co_borrower_default_multi_bureau_retry_ |
| mfi-los | indl_qde_co_borrower_qde_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_qde_co_borrower_qde_multi_bureau_retry_ |
| mfi-los | indl_qde_borrower_conduct_pd_factiva_service_ | 3000 | 1 | 1 | indl_qde_borrower_conduct_pd_factiva_ |
| mfi-los | indl_qde_borrower_conduct_pd_posidex_service_ | 5000 | 1 | 1 | indl_qde_borrower_conduct_pd_posidex_ |
| mfi-los | indl_qde_borrower_conduct_pd_posidex_service_second_call_ | 6000 | 1 | 1 | indl_qde_borrower_conduct_pd_posidex_second_call_ |
| mfi-los | indl_qde_borrower_conduct_pd_multi_bureau_service_ | 6000 | 1 | 1 | indl_qde_borrower_conduct_pd_multi_bureau_ |
| mfi-los | indl_qde_co_borrower_conduct_pd_factiva_service_ | 3000 | 1 | 1 | indl_qde_co_borrower_conduct_pd_factiva_ |
| mfi-los | indl_qde_co_borrower_conduct_pd_posidex_service_ | 5000 | 1 | 1 | indl_qde_co_borrower_conduct_pd_posidex_ |
| mfi-los | indl_qde_co_borrower_conduct_pd_posidex_service_second_call_ | 6000 | 1 | 1 | indl_qde_co_borrower_conduct_pd_posidex_second_call_ |
| mfi-los | indl_qde_co_borrower_conduct_pd_multi_bureau_service_ | 6000 | 1 | 1 | indl_qde_co_borrower_conduct_pd_multi_bureau_ |
| mfi-los | indl_cm_dashboard_borrower_default_factiva_service_ | 3000 | 1 | 1 | indl_cm_dashboard_borrower_factiva_ |
| mfi-los | indl_cm_dashboard_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | indl_cm_dashboard_borrower_default_factiva_retry_ |
| mfi-los | indl_cm_dashboard_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_cm_dashboard_borrower_default_internal_dedupe_retry_ |
| mfi-los | indl_cm_dashboard_borrower_default_posidex_service_ | 5000 | 1 | 1 | indl_cm_dashboard_borrower_posidex_ |
| mfi-los | indl_cm_dashboard_borrower_default_posidex_service_second_call_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_posidex_second_call_ |
| mfi-los | indl_cm_dashboard_borrower_default_multi_bureau_service_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_multi_bureau_ |
| mfi-los | indl_cm_dashboard_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | indl_cm_dashboard_borrower_default_posidex_retry_ |
| mfi-los | indl_cm_dashboard_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_default_posidex_second_call_retry_ |
| mfi-los | indl_cm_dashboard_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_default_multi_bureau_retry_ |
| mfi-los | indl_cm_dashboard_borrower_posidex_service_ | 5000 | 1 | 1 | indl_cm_dashboard_borrower_posidex_ |
| mfi-los | indl_cm_dashboard_borrower_factiva_service_ | 3000 | 1 | 1 | indl_cm_dashboard_borrower_factiva_ |
| mfi-los | indl_cm_dashboard_borrower_posidex_service_second_call_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_posidex_second_call_ |
| mfi-los | indl_cm_dashboard_borrower_multi_bureau_service_ | 6000 | 1 | 1 | indl_cm_dashboard_borrower_multi_bureau_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_factiva_service_ | 3000 | 1 | 1 | indl_cm_dashboard_co_borrower_factiva_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | indl_cm_dashboard_co_borrower_default_factiva_retry_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | indl_cm_dashboard_co_borrower_default_internal_dedupe_retry_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_posidex_service_ | 5000 | 1 | 1 | indl_cm_dashboard_co_borrower_posidex_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_posidex_service_second_call_ | 6000 | 1 | 1 | indl_cm_dashboard_co_borrower_posidex_second_call_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_multi_bureau_service_ | 6000 | 1 | 1 | indl_cm_dashboard_co_borrower_multi_bureau_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | indl_cm_dashboard_co_borrower_default_posidex_retry_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | indl_cm_dashboard_co_borrower_default_posidex_second_call_retry_ |
| mfi-los | indl_cm_dashboard_co_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | indl_cm_dashboard_co_borrower_default_multi_bureau_retry_ |
| mfi-los | jlgdl_qde_borrower_onboarding_factiva_service_ | 4000 | 3 | 1 | jlgdl_qde_borrower_onboarding_factiva_ |
| mfi-los | jlgdl_qde_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | jlgdl_qde_borrower_default_factiva_retry_ |
| mfi-los | jlgdl_qde_borrower_qde_factiva_service_retry_ | 3000 | 1 | 1 | jlgdl_qde_borrower_qde_factiva_retry_ |
| mfi-los | jlgdl_qde_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | jlgdl_qde_borrower_default_internal_dedupe_retry_ |
| mfi-los | jlgdl_qde_borrower_qde_internal_dedupe_service_retry_ | 3000 | 1 | 1 | jlgdl_qde_borrower_qde_internal_dedupe_retry_ |
| mfi-los | jlgdl_qde_borrower_onboarding_posidex_service_ | 5000 | 1 | 1 | jlgdl_qde_borrower_onboarding_posidex_ |
| mfi-los | jlgdl_qde_borrower_onboarding_posidex_service_second_call_ | 6000 | 1 | 1 | jlgdl_qde_borrower_onboarding_posidex_second_call_ |
| mfi-los | jlgdl_qde_borrower_onboarding_multi_bureau_service_ | 6000 | 1 | 1 | jlgdl_qde_borrower_onboarding_multi_bureau_ |
| mfi-los | jlgdl_qde_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | jlgdl_qde_borrower_default_posidex_retry_ |
| mfi-los | jlgdl_qde_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | jlgdl_qde_borrower_default_posidex_second_call_retry_ |
| mfi-los | jlgdl_qde_borrower_qde_posidex_service_retry_ | 5000 | 1 | 1 | jlgdl_qde_borrower_qde_posidex_service_retry_ |
| mfi-los | jlgdl_qde_borrower_qde_posidex_service_second_call_retry_ | 6000 | 1 | 1 | jlgdl_qde_borrower_qde_posidex_service_second_call_retry_ |
| mfi-los | jlgdl_qde_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | jlgdl_qde_borrower_default_multi_bureau_retry_ |
| mfi-los | jlgdl_qde_borrower_qde_multi_bureau_service_retry_ | 6000 | 1 | 1 | jlgdl_qde_borrower_qde_multi_bureau_retry_ |
| mfi-los | jlgdl_qde_borrower_conduct_bet_factiva_service_ | 3000 | 2 | 1 | jlgdl_qde_borrower_conduct_bet_factiva_ |
| mfi-los | jlgdl_qde_borrower_conduct_bet_posidex_service_ | 5000 | 1 | 1 | jlgdl_qde_borrower_conduct_bet_posidex_ |
| mfi-los | jlgdl_qde_borrower_conduct_bet_posidex_service_second_call_ | 6000 | 1 | 1 | jlgdl_qde_borrower_conduct_bet_posidex_second_call_ |
| mfi-los | jlgdl_qde_borrower_conduct_bet_multi_bureau_service_ | 6000 | 1 | 1 | jlgdl_qde_borrower_conduct_bet_multi_bureau_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_factiva_service_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_borrower_factiva_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_factiva_service_retry_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_borrower_default_factiva_retry_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_internal_dedupe_service_retry_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_borrower_default_internal_dedupe_retry_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_posidex_service_ | 5000 | 1 | 1 | jlgdl_cm_dashboard_borrower_posidex_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_borrower_posidex_second_call_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_multi_bureau_service_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_borrower_multi_bureau_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_posidex_service_retry_ | 5000 | 1 | 1 | jlgdl_cm_dashboard_borrower_default_default_posidex_retry_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_posidex_service_second_call_retry_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_borrower_default_posidex_second_call_retry_ |
| mfi-los | jlgdl_cm_dashboard_borrower_default_multi_bureau_service_retry_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_borrower_default_multi_bureau_retry_ |
| mfi-los | jlgdl_cm_dashboard_factiva_service_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_factiva_service_ |
| mfi-los | jlgdl_cm_dashboard_factiva_service_retry_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_factiva_service_retry_ |
| mfi-los | jlgdl_cm_dashboard_internal_dedupe_service_retry_ | 2000 | 1 | 1 | jlgdl_cm_dashboard_internal_dedupe_service_retry_ |
| mfi-los | jlgdl_cm_dashboard_internal_dedupe_retry_ | 3000 | 1 | 1 | jlgdl_cm_dashboard_internal_dedupe_retry_ |
| mfi-los | jlgdl_cm_dashboard_posidex_service_ | 5000 | 1 | 1 | jlgdl_cm_dashboard_posidex_service_ |
| mfi-los | jlgdl_cm_dashboard_posidex_service_second_call_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_posidex_service_second_call_ |
| mfi-los | jlgdl_cm_dashboard_multi_bureau_service_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_multi_bureau_service_ |
| mfi-los | jlgdl_cm_dashboard_posidex_service_retry_ | 5000 | 1 | 1 | jlgdl_cm_dashboard_posidex_service_retry_ |
| mfi-los | jlgdl_cm_dashboard_posidex_service_second_call_retry_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_posidex_service_second_call_retry_ |
| mfi-los | jlgdl_cm_dashboard_multi_bureau_service_retry_ | 6000 | 1 | 1 | jlgdl_cm_dashboard_multi_bureau_service_retry_ |
| mfi-los | jlgdl_household_details_factiva_service_ | 3000 | 3 | 1 | jlgdl_household_details_factiva_service_ |
| mfi-los | jlgdl_household_details_factiva_service_retry_ | 3000 | 1 | 1 | jlgdl_household_details_factiva_service_retry_ |
| mfi-los | jlgdl_household_details_internal_dedupe_service_retry_ | 3000 | 1 | 1 | jlgdl_household_details_internal_dedupe_service_retry_ |
| mfi-los | jlgdl_household_details_internal_dedupe_retry_ | 3000 | 1 | 1 | jlgdl_household_details_internal_dedupe_retry_ |
| mfi-los | jlgdl_household_details_posidex_service_ | 5000 | 1 | 1 | jlgdl_household_details_posidex_ |
| mfi-los | jlgdl_household_details_posidex_service_second_call_ | 6000 | 1 | 1 | jlgdl_household_details_posidex_second_call_ |
| mfi-los | jlgdl_household_details_multi_bureau_service_ | 6000 | 1 | 1 | jlgdl_household_details_multi_bureau_ |
| mfi-los | jlgdl_household_details_posidex_service_retry_ | 5000 | 1 | 1 | jlgdl_household_details_posidex_retry_ |
| mfi-los | jlgdl_household_details_posidex_service_second_call_retry_ | 6000 | 1 | 1 | jlgdl_household_details_posidex_second_call_retry_ |
| mfi-los | jlgdl_household_details_multi_bureau_service_retry_ | 6000 | 1 | 1 | jlgdl_household_details_multi_bureau_retry_ |
| mfi-los | offline_data_bet_ | 3000 | 1 | 1 | offline_data_bet_ |
| mfi-los | offline_data_pd_ | 3000 | 1 | 1 | offline_data_pd_ |
| mfi-los | offline_data_test_ | 3000 | 1 | 1 | offline_data_test_ |
| mfi-los | offline_data_td_ | 3000 | 1 | 1 | offline_data_td_ |
| mfi-los | ckyc_preprocess_api_ | 3000 | 2 | 2 | ckyc_preprocess_api_ |
| mfi-los | los_lms_data_sync_ | 5000 | 2 | 2 | los_lms_data_sync_ |
| mfi-los | generate_consent_doc_ | 5000 | 2 | 2 | generate_consent_doc_ |
| mfi-los | generate_specific_loan_doc_ | 5000 | 1 | 1 | generate_specific_loan_doc_ |
| mfi-los | save_mmi_request_response_ | 5000 | 1 | 1 | save_mmi_request_response |
| mfi-los | los_lms_disbursement_sync | 5000 | 3 | 3 | los_lms_disbursement_sync |
| platform-accounting-v2 | bulk_collection_data_failed_ | 100 | 1 | (unset) | bulk_collection_failed_record_consumer |
| platform-accounting-v2 | disburse_loan_api_ | 100 | 1 | (unset) | disburse_loan_api_consumer_ |
| platform-actor | posidex_actor_inbound_ | 5000 | 1 | (unset) | posidex_inbound_actor_consumer |
| platform-actor | session_activity_login_ | 100 | 1 | 1 | session_activity_ |
| platform-actor | session_activity_logout | 100 | 1 | 1 | session_activity_ |
| platform-actor | update_customer_loan_details | 100 | 1 | 1 | loan_details_ |
| platform-audit | audit_ | 1000 | 1 | 1 | consumer_id_audit_ |
| platform-audit | telemetry_perf_log_ | 5000 | 1 | 50 | telemetry_perf_log_ |
| platform-audit | external_service_audit_ | 1000 | 1 | 1 | external_service_audit_ |
| platform-audit | api_gateway_request_ | 1000 | 10 | 10 | consumer_id_api_gateway_request_ |
| platform-audit | api_gateway_response_ | 1000 | 10 | 10 | consumer_id_api_gateway_response_ |
| platform-notifications | async_notifications_ | 1000 | 1 | 10 | consumer_id_notification_ |
| platform-notifications | alerts | 1000 | 1 | 10 | consumer_id_notification_ |
| platform-notifications | notification_sms_ | 1000 | 1 | 10 | notification_sms_consumer_ |
| platform-notifications | notification_fcm_ | 1000 | 1 | 10 | notification_fcm_consumer_ |
| platform-notifications | notification_email_ | 1000 | 1 | 10 | notification_email_consumer_ |
| platform-payments | collection_customer_details_ | 100 | 1 | 1 | collection_customer_details_ |
| platform-payments | meeting_center_details_ | 100 | 1 | 1 | collection_meeting_center_details_ |
| platform-payments | bulk_collection_data_ | 1500 | 1 | 1 | bulk_collection_data_consumer_ |
| platform-payments | collection_office_details_ | 3000 | 1 | 1 | collection_office_details_consumer_ |
| platform-payments | update_collection_task_details_ | 1000 | 1 | 1 | update_collection_task_details_consumer_ |
| platform-payments | collection_primary_allocation_ | 1000 | 1 | 1 | collection_primary_allocation_consumer_ |
| platform-payments | collection_secondary_allocation_ | 3000 | 1 | 1 | collection_secondary_allocation_consumer_ |
| platform-payments | collection_task_processing_ | 3000 | 1 | 1 | collection_task_creation_consumer_ |
| platform-task | task_user_tat_ | 3000 | 8 | 1 | task_user_tat_ |
| platform-task | collection_task_creation_ | 1000 | 1 | 1 | collection_task_creation_consumer_ |
| platform-task | finnone_collection_task_creation_ | 1000 | 4 | 1 | finnone_collection_task_creation_consumer_ |

### 3a) Thread-weighted consumers per service (sum of `numberOfThreads`)

| Service | Consumer rows | Sum of threads |

|---------|---------------|----------------|

| mfi-los | 119 | 131 |
| platform-accounting-v2 | 2 | 2 |
| platform-actor | 4 | 4 |
| platform-audit | 5 | 23 |
| platform-notifications | 5 | 5 |
| platform-payments | 8 | 8 |
| platform-task | 3 | 13 |

## 4) Redis — URL / DB index / TTL-like (application.properties)

| Service | novopay.service.redis.url | novopay.service.redis.db.index | TTL / STAN keys |

|---------|---------------------------|--------------------------------|-----------------|

| novopay-mfi-los |  |  | (none explicit) |
| novopay-platform-accounting-v2 |  |  | (none explicit) |
| novopay-platform-actor |  |  | (none explicit) |
| novopay-platform-api-gateway | redis://127.0.0.1:6379/ | 0 | novopay.service.gateway.long.stan.ttl.millisecond=600000 |
| novopay-platform-approval |  |  | (none explicit) |
| novopay-platform-audit |  |  | (none explicit) |
| novopay-platform-authorization |  |  | (none explicit) |
| novopay-platform-batch |  |  | (none explicit) |
| novopay-platform-dms |  |  | (none explicit) |
| novopay-platform-lib |  |  | (none explicit) |
| novopay-platform-masterdata-management |  |  | (none explicit) |
| novopay-platform-notifications |  |  | spring.mail.properties.mail.smtp.starttls.enable=true |
| novopay-platform-payments |  |  | (none explicit) |
| novopay-platform-simulators |  |  | (none explicit) |
| novopay-platform-task |  |  | (none explicit) |
| trustt-platform-reporting |  |  | (none explicit) |

## 5) Thread pools / executor hints in properties

Most pool sizing is **Java `@Configuration`** (`AsyncConfig`, batch `TaskExecutor`). Scanned properties:

| Service | matching keys |

|---------|---------------|

| novopay-mfi-los | (none in properties) |
| novopay-platform-accounting-v2 | (none in properties) |
| novopay-platform-actor | (none in properties) |
| novopay-platform-api-gateway | (none in properties) |
| novopay-platform-approval | (none in properties) |
| novopay-platform-audit | (none in properties) |
| novopay-platform-authorization | (none in properties) |
| novopay-platform-batch | (none in properties) |
| novopay-platform-dms | (none in properties) |
| novopay-platform-lib | (none in properties) |
| novopay-platform-masterdata-management | (none in properties) |
| novopay-platform-notifications | (none in properties) |
| novopay-platform-payments | (none in properties) |
| novopay-platform-simulators | chameleon.datasource.maximum.pool.size |
| novopay-platform-task | (none in properties) |
| trustt-platform-reporting | (none in properties) |

## 6) Drift risk — same semantic, different literal

| Observation | Risk |

|-------------|------|

| `message.broker.bootstrap.servers` uses `http://127.0.0.1:9092` vs `http://localhost:9092` | Local OK; prod must template consistently |

| Gateway `novopay.internal.api.socket.timeout=10000` vs payments IDFC `socket.timeout=120000` | Callee-specific vs gateway default — orchestration may pass different millis |

| Actor email password / ES password in **clear** properties | **Secret drift** / leak risk — Vault disabled (`spring.cloud.vault.enabled=false`) |

| Duplicate `spring.main.allow-bean-definition-overriding` / circular refs toggles | Boot behaviour differs if one service omits |


## 7) Hardcoded URLs in `application.properties` (should be env-specific)

### novopay-mfi-los

- `novopay.platform.es.server.path` = `http://127.0.0.1:9200`
- `novopay.dms.server.url` = `http://localhost:8480/dms/`
- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-accounting-v2

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-actor

- `novopay.platform.es.server.path` = `http://127.0.0.1:9200`
- `novopay.dms.server.url` = `http://localhost:8480/dms/`
- `message.broker.bootstrap.servers` = `http://localhost:9092`

### novopay-platform-api-gateway

- `bpmn.server.host` = `https://mfiapp.novopay.in:`
- `content.security.policy` = `"default-src 'self' https://maps.googleapis.com *.mappls.com *.mapmyindia.com; style-src 'self' 'unsafe-inline' https://`
- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-approval

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-audit

- `novopay.platform.es.server.path` = `http://127.0.0.1:9200`
- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-authorization

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-dms

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-masterdata-management

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`

### novopay-platform-notifications

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`
- `app.firebase-db-url` = `https://digital-collections-51246.firebaseio.com`

### novopay-platform-payments

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`
- `better.place.equitas.imps.url` = `http://192.168.150.2:8686/chameleon/forward/json/imps`
- `better.place.equitas.imps.status.url` = `http://192.168.150.2:8686/chameleon/forward/json/impsStatus`
- `idfc.service.create.ngo.connect.cabinet.service.url` = `https://uat-idfc-api.novopay.in/novopay_uat/omnidocs_ws/services/NGOConnectionServiceImpl?wsdl`
- `idfc.service.create.ngo.search.folder.service.url` = `https://uat-idfc-api.novopay.in/novopay_uat/omnidocs_ws/services/NGOSearchFolderServiceImp?wsdl`
- `idfc.service.create.ngo.adddoc.serviceurl` = `https://uat-idfc-api.novopay.in/novopay_uat/omnidocs_ws/services/NGOAddDocServiceImp?wsdl`
- `idfc.sr.signature.add.sub.folder.omni.docs` = `https://uat-idfc-api.novopay.in/novopay_uat/omnidocs_ws/services/NGOAddFolServiceImp?wsdl`
- `idfc.service.create.ngo.disconnect.serviceurl` = `https://uat-idfc-api.novopay.in/novopay_uat/omnidocs_ws/services/NGOConnectionServiceImpl?wsdl`
- `idfc.crm.non.ekyc.service.url` = `https://uat-idfc-api.novopay.in/novopay_uat/Services/MicroATMAdapter/CreateMicroATMWorkItemDetails_01`
- `idfc.crm.non.ekyc.status.service.url` = `https://uat-idfc-api.novopay.in/novopay_uat/Services/MicroATMAdapter/GetMicroATMWorkItemStatus_01`
- `idfc.imps.service.url` = `https://sit-idfc.novopay.in/novopay_uat/IMPSServices`

### novopay-platform-task

- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`
- `novopay.platform.es.server.path` = `http://127.0.0.1:9200`

### trustt-platform-reporting

- `dmsEndPoint` = `https://dev1-mfi.novopay.in/api-gateway/document/v1/uploadDocument`
- `message.broker.bootstrap.servers` = `http://127.0.0.1:9092`
- `novopay.platform.es.server.path` = `https://172.31.2.221:6200`


## 8) Hardcoded URLs in Java (sample — not exhaustive)

Run `grep -R "https://" novopay-*/src/main/java` for full list. Notable patterns:

- BPMN / bureau callback hosts in gateway `application.properties` (`bpmn.server.host`)

- `novopay.dms.server.url=http://localhost:8480/dms/` in actor properties

- `novopay.platform.es.server.path=http://127.0.0.1:9200` actor

- Lib templates / bank integrations often embed partner base URLs in JTF or Java constants — **out of scope** for this properties scan


## 9) Missing properties (one service has, others do not)

- `novopay.internal.api.socket.timeout` only on: **novopay-platform-api-gateway** — other services rely on **per-call** args or defaults.

- `spring.kafka.bootstrap-servers` present on: **novopay-platform-accounting-v2, novopay-platform-api-gateway**; others may inherit only from message broker XML / empty.


## 10) Operational checklist

1. Align **bootstrap** URL scheme (`http` vs `PLAINTEXT`) with broker listener security.

2. Document **default** `max.poll.interval.ms` at broker + Spring level — not visible in XML.

3. Move secrets out of `application.properties` into vault / K8s secrets.

4. Add `spring.kafka.consumer.*` explicitly if you need cross-service uniformity.


---

*Rebuild 2026-04-10.*
