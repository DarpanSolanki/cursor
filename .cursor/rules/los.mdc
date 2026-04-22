---
description: "Auto-loads when editing novopay-mfi-los"
globs:
  - "**/novopay-mfi-los/**/*.java"
  - "**/novopay-mfi-los/**/*.xml"
alwaysApply: false
---

# LOS Module — Active Intelligence

## Critical context before any edit

- LOS is a **disbursement originator** and origination hub
- LOS → Kafka (`disburse_loan_api_`) → accounting `LmsMessageBrokerConsumer` is a core money path
- **Redis** in-flight / dedupe on disburse path: **TTL gap** called out in `gaps-and-risks.md` — verify before changing keys
- **DisbursementSyncService** / `entity_type`: contract vs accounting sync payload — **High** gap pair in `gaps-and-risks.md`
- LOS is a **dependency hub** for origination; many flows start here (see `.cursor/service-dependency-graph.md`)

## Before touching disbursement or sync

1. `.cursor/accounting-flows.md` + `system_brain/flows/disbursement.md` as needed
2. `entity_type` + sync rows in `gaps-and-risks.md`
3. Redis key behaviour on LOS producer path
4. Trace: LOS produce → `disburse_loan_api_*` → accounting consumer → `los_lms_disbursement_sync*` → `DisbursementSyncConsumer` / `DisbursementSyncService`

## After any edit

- Update `accounting-flows.md` or `system_brain/` if end-to-end disburse/sync behaviour changes
- Update `event-registry.md` if topic or payload contract changes
- Append `.cursor/changelog.md`
