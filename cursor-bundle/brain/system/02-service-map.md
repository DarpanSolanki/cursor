# 02 · Service map — single-page reference

> Every service, in one table. For deeper context on each, follow the link to [`../services/<name>.md`](../services/).

## Backend services (Java / Spring)

| # | Service | Java root pkg | DB schema | Primary role | Brain doc |
|--:|---|---|---|---|---|
| 1 | `novopay-mfi-los` | `in.novopay.los` | `mfi_los` | LOS — application capture, KYC, eligibility, underwriting, disbursement-trigger | [los](../services/novopay-mfi-los.md) |
| 2 | `novopay-platform-accounting-v2` | `in.novopay.accounting` | `mfi_accounting` | **LMS core** — loan account, GL, accruals, EOD/BOD, NPA | [accounting](../services/novopay-platform-accounting-v2.md) |
| 3 | `novopay-platform-actor` | `in.novopay.actor` | `mfi_actor` | Mini-CRM — customer/employee/office/role/hierarchy/use-case | [actor](../services/novopay-platform-actor.md) |
| 4 | `novopay-platform-payments` | `in.novopay.payments` | `mfi_payments` | LCS — collections, NACH, Razorpay, Finnone+VYMO sync | [payments](../services/novopay-platform-payments.md) |
| 5 | `novopay-platform-batch` | `in.novopay.batch` | `mfi_batch` | Scheduler + bulk-upload registry | [batch](../services/novopay-platform-batch.md) |
| 6 | `novopay-platform-approval` | `in.novopay.approval` | `mfi_approval` | Maker-checker engine | [approval](../services/novopay-platform-approval.md) |
| 7 | `novopay-platform-task` | `in.novopay` | `mfi_task` | Operator tasks, TAT, delegation, BPMN | [task](../services/novopay-platform-task.md) |
| 8 | `novopay-platform-audit` | `in.novopay.audit` | `mfi_audit` | Req/resp logging (DB) + functional audit (ES) | [audit](../services/novopay-platform-audit.md) |
| 9 | `novopay-platform-masterdata-management` | `in.novopay.masterdata` | `mfi_masterdata` | Code masters, configurations | [masterdata](../services/novopay-platform-masterdata-management.md) |
| 10 | `novopay-platform-notifications` | `in.novopay.notifications` | `mfi_notifications` | SMS / Email / FCM / OTP | [notifications](../services/novopay-platform-notifications.md) |
| 11 | `novopay-platform-dms` | `in.novopay.dms` | (single cluster) | Document store (FS / S3) | [dms](../services/novopay-platform-dms.md) |
| 12 | `novopay-platform-authorization` | `in.novopay.authorization` | `mfi_authorization` | Roles, permissions, usecase access | [authorization](../services/novopay-platform-authorization.md) |
| 13 | `novopay-platform-api-gateway` | `in.novopay.apigateway` | `mfi_api_gateway` | Single entry, routing, dedup, callbacks | [api-gateway](../services/novopay-platform-api-gateway.md) |
| 14 | `novopay-platform-initial-setup` | (Flyway runner) | seeds all schemas | Bootstrap — tenant master + ~700 APIs + GL chart + roles | [initial-setup](../services/novopay-platform-initial-setup.md) |
| 15 | `novopay-platform-lib` | `in.novopay.infra.*` | (lib only) | Shared infra — orchestration, navigation, cache, kafka, batch | [lib](../services/novopay-platform-lib.md) |
| 16 | `trustt-platform-reporting` | `in.novopay` | yugabyte | EOD + scheduled reports (RBI ADF, UAM, Posidex) | [reporting](../services/trustt-platform-reporting.md) |

## Frontend

| # | Service | Stack | Role | Brain doc |
|--:|---|---|---|---|
| 17 | `novopay-platform-webapp` | Angular 20 | Operator-facing SPA (~65 lazy modules) | [webapp](../services/novopay-platform-webapp.md) |

## Dependency at a glance

The closer to "money/state changes" a service is, the more it's depended on:

```
            Most-depended (called by everyone)
                       │
                  ┌────┴────┐
                  │  actor  │              ← getUserDetails / getOfficeDetails / etc.
                  ├─────────┤
                  │masterdata│              ← code masters, validators
                  ├─────────┤
                  │ accounting│            ← postTransaction, loanRepayment, getLoanAccount, etc.
                  ├─────────┤
                  │approval  │             ← submitApplication
                  ├─────────┤
                  │  task    │             ← createOrUpdateTask
                  ├─────────┤
                  │notifications│          ← getNotificationMessage
                  ├─────────┤
                  │   dms    │             ← verifyDocuments
                  ├─────────┤
                  │  audit   │             ← framework auto
                  ├─────────┤
                  │authorization│           ← gateway-side check (per request)
                  ├─────────┤
                  │   batch   │             ← scheduler (one-way out)
                  ├─────────┤
                  │   los    │             ← origination only
                  ├─────────┤
                  │ payments │             ← collection only
                  └─────────┘
                  Least-depended (terminal services)
```

## Inter-service edges

- **Sync HTTP**: routed through gateway via `NovopayInternalAPIClient.callInternalAPI(...)`. The bean lives in `infra-service-gateway` lib.
- **Async Kafka**: per-service `MessageBroker.xml` declares producers/consumers. Topic prefixes are tenant-scoped (`<topic>_<tenant>`).
- See [`05-integration-topology.md`](05-integration-topology.md) for the full edge map.

## What every service has

- `.cursorrules` at repo root — service team's declaration of scope.
- `deploy/application/orchestration/*.xml` — Request → processor chains.
- `deploy/application/messagebroker/MessageBroker.xml` — Kafka declarations.
- `src/main/java/in/novopay/<service>/` — Java root.
- `src/main/resources/application*.properties` — service config.
- A few have `flyway/` migrations; most rely on `initial-setup` for schema.

## Branch + workspace state

All on `mfi_integration_v3.2.8.4.1`. Per-repo SHA snapshot: [`../workspace-state.md`](../workspace-state.md).
