# Services — one brain doc per service

> Each file in this folder is a **single-page mental model** of one service. It tells you what the service owns, what it depends on, what depends on it, and where to look in code. It is *not* a re-statement of the service's CLAUDE.md — it is a synthesis after probing the actual orchestration XMLs, Kafka config, and entity packages on branch `mfi_integration_v3.2.8.4.1`.

The 17 services in this workspace are:

| Service | Role in LMS | File |
|---|---|---|
| `novopay-mfi-los` | Loan Origination System (LOS) — application capture, KYC, eligibility, underwriting, disbursement-trigger | [novopay-mfi-los.md](novopay-mfi-los.md) |
| `novopay-platform-accounting-v2` | Loan Management System (LMS) — ledger, GL, accruals, EOD/BOD, NPA, the *core* of LMS | [novopay-platform-accounting-v2.md](novopay-platform-accounting-v2.md) → links to deep-dive |
| `novopay-platform-actor` | Mini-CRM — customer / employee / office / role / hierarchy / use-case master | [novopay-platform-actor.md](novopay-platform-actor.md) |
| `novopay-platform-payments` | Loan Collection System (LCS) — collections, NACH, Razorpay, Finnone+VYMO sync | [novopay-platform-payments.md](novopay-platform-payments.md) |
| `novopay-platform-batch` | Scheduler + bulk-upload registry; one-way calls into accounting/LOS by `<Request name>` | [novopay-platform-batch.md](novopay-platform-batch.md) |
| `novopay-platform-approval` | Maker-checker engine; owns drafts + workflow, target-API replay on approval | [novopay-platform-approval.md](novopay-platform-approval.md) |
| `novopay-platform-task` | Operator task store, TAT/escalation, delegation, BPMN tasks | [novopay-platform-task.md](novopay-platform-task.md) |
| `novopay-platform-audit` | Centralised request/response logging (DB) + functional audit search (Elasticsearch) | [novopay-platform-audit.md](novopay-platform-audit.md) |
| `novopay-platform-masterdata-management` | Code masters, configurations, cache hub | [novopay-platform-masterdata-management.md](novopay-platform-masterdata-management.md) |
| `novopay-platform-notifications` | Multi-channel notifications (SMS / Email / FCM / OTP), templates, code-mapping | [novopay-platform-notifications.md](novopay-platform-notifications.md) |
| `novopay-platform-dms` | Document store, dual storage backend (FS / S3), `verifyDocuments` for disbursement | [novopay-platform-dms.md](novopay-platform-dms.md) |
| `novopay-platform-authorization` | Roles, permissions, usecase-based access enforcement | [novopay-platform-authorization.md](novopay-platform-authorization.md) |
| `novopay-platform-api-gateway` | Single entry, session+permission validation, STAN dedup, request forwarding, callbacks | [novopay-platform-api-gateway.md](novopay-platform-api-gateway.md) |
| `novopay-platform-initial-setup` | Flyway-based bootstrap; ~700 API definitions, master tenants, GL chart, roles | [novopay-platform-initial-setup.md](novopay-platform-initial-setup.md) |
| `novopay-platform-lib` | Shared infra (orchestration, navigation, cache, kafka, masterdata, batch builders) | [novopay-platform-lib.md](novopay-platform-lib.md) |
| `novopay-platform-webapp` | Angular 20 admin SPA — single-project, ~65 lazy modules, talks via gateway | [novopay-platform-webapp.md](novopay-platform-webapp.md) |
| `trustt-platform-reporting` | EOD + scheduled reports (RBI ADF, UAM, Posidex extracts) — DMS upload, ES audit | [trustt-platform-reporting.md](trustt-platform-reporting.md) |

## How to use this folder

- **Investigating any one service** → read its file first; cross-link to the cited orchestration XML / package.
- **Investigating a flow** that crosses services → read [`../flows/`](../flows/) instead; they cite back into these service docs.
- **Investigating an LMS-internal concern** (GL hit, repayment math, NPA) → start in [`../accounting/`](../accounting/) — the deepest single-service bundle.
- **Looking for the API of a Request** → use the system KG (`claude/kg/bin/kg flow <request>` / `kg search`).

## Key conventions visible across all services

- Every service has `deploy/application/orchestration/*.xml` defining `<Request name="…">` → `<Processor bean="…">` chains.
- Every service has `deploy/application/messagebroker/MessageBroker.xml` declaring producers/consumers.
- Every service has a CLAUDE.md at the repo root — that is the **service team's** declaration of scope. Use it as the starting fact, then verify against code.
- Java root packages all start with `in.novopay.<service>` (the older actor service uses `in.novopay.actor`; reporting uses `in.novopay`).
- DB schemas all start with `mfi_<service>` for MFI tenant. Multi-tenant deployments may use different prefixes per tenant.
- All services are on branch `mfi_integration_v3.2.8.4.1` (verified — see [../workspace-state.md](../workspace-state.md)).
