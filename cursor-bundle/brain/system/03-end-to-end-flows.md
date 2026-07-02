# 03 · End-to-end flows — overview

> The major user journeys, mapped to which services + which Requests they hit. Each row has a deeper narrative under [`../flows/`](../flows/).

## Customer + group lifecycle

| Journey | Services touched | Detail |
|---|---|---|
| Customer onboarding | LOS → actor → DMS → masterdata → notifications (OTP) → audit | [`../flows/customer-onboarding.md`](../flows/customer-onboarding.md) |
| Group formation (SHG/JLG) | LOS → actor → masterdata | [`../flows/customer-onboarding.md`](../flows/customer-onboarding.md) §"Group formation" |
| Loan application + underwriting | LOS → actor → masterdata → DMS → notifications → BRE/Bureau (async Kafka) → approval → task | [`../flows/loan-application-underwriting.md`](../flows/loan-application-underwriting.md) |
| Disbursement (LOS → accounting → bank) | LOS → Kafka → accounting → DMS (verifyDocuments) → bank NEFT → accounting (PARENT_SUCCESS) → child fan-out (queue → batch) → LOS callback | [`../flows/disbursement-end-to-end.md`](../flows/disbursement-end-to-end.md) |
| Repayment (collection → accounting) | webapp / payments → accounting (`loanRepayment`) → appropriation → `postTransaction` → loan_due_details / GL → notifications | [`../flows/repayment-end-to-end.md`](../flows/repayment-end-to-end.md) |
| SHG / JLG fan-out | accounting parent flow → `loan_account_events_queue` → `childLoanEventProcessingBatchJob` → child Requests | [`../flows/shg-jlg-group-loan.md`](../flows/shg-jlg-group-loan.md) |
| Foreclosure & closure | webapp → accounting `loanForeclosure` (or `childLoanForeclosure`) → maker/checker → posting → auto-closure | [`../flows/foreclosure-and-closure.md`](../flows/foreclosure-and-closure.md) |
| NPA promotion + provisioning | EOD pipeline (DPD calc → asset criteria → asset classification → derived fields → provisioning) | [`../flows/npa-and-provisioning.md`](../flows/npa-and-provisioning.md) |
| EOD / BOD daily cycle | batch service → accounting `runEODJobs` / `runBODJobs` → fans out to per-job Requests | [`../flows/eod-bod-cycle.md`](../flows/eod-bod-cycle.md) |
| Maker-checker (any flow) | originating service → approval `submitApplication` → checker action → target Request replay | [`../flows/maker-checker.md`](../flows/maker-checker.md) |

## Operational journeys

| Journey | Services |
|---|---|
| Tenant onboarding (cluster bootstrap) | initial-setup (Flyway) — see [`../services/novopay-platform-initial-setup.md`](../services/novopay-platform-initial-setup.md) and [`../runbooks/tenant-bootstrap.md`](../runbooks/tenant-bootstrap.md) |
| Bulk file ingest (e.g. NOC, manual JE, foreclosure-charge update) | webapp → batch `bulkUploadBatch` → accounting `bulkFileToSG…Job` + `bulkSGTo…Job` |
| Reporting (RBI ADF / UAM / Posidex / MIS) | accounting `generatePostEODReports` → reporting service `generateReport` → DMS upload + ES audit |
| Operator task lifecycle | originating service `createOrUpdateTask` → task service → escalation (`tat_escalation_matrix`) → close (`updateTaskStatusAndCallApi`) |

## Cross-cutting concerns (apply to every flow)

- **Validation** — every Request has a `<Validators>` block (mandatoryFieldValidator, patternFieldValidator, masterDataValidator, numberValidator, stringLengthValidator) executed before any processor runs.
- **Tenant isolation** — `ThreadLocalContext.tenant` resolved at gateway, propagated through every internal call.
- **Audit emit** — `<AuditData>` element on processors → framework writes to `audit_log` async via Kafka topics consumed by audit service.
- **Maker-checker** — Control-pattern wrapper on every state-changing master CRUD; maker creates draft + workflow row, checker re-fires the same Request with `function_code=APPROVE`.
- **Idempotency** — `client_reference_number` on `postTransaction`; STAN at gateway; `getApiResponseByStan` for retries.

## How to navigate this folder

- Strategic question (e.g. "how does a SHG loan get disbursed end-to-end?") → start at the [flows table](#customer--group-lifecycle), follow the link.
- Tactical question (e.g. "why did this single repayment post wrong?") → go straight to [`../runbooks/`](../runbooks/) or [`../accounting/10-debugging-runbook.md`](../accounting/10-debugging-runbook.md).
- Money question ("what GLs hit when X happens?") → [`04-money-flow-rupee-journey.md`](04-money-flow-rupee-journey.md) and [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md).
