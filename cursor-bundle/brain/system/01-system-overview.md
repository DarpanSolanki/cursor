# 01 · Trustt LMS — system overview

## What this platform is

Trustt's MFI lending platform is a tenant-multiplexed digital lending system specialised for **microfinance** — predominantly **SHG (Self-Help Group)** and **JLG (Joint Liability Group)** lending, plus individual MFI loans. It runs the full lifecycle: customer onboarding → loan application → underwriting → disbursement → servicing (repayment, restructuring, foreclosure, closure, NPA management) → reporting.

The platform is split into **17 services** (16 backend + 1 Angular SPA) on a shared `infra-*` library. The functional centre of LMS is the **accounting** service, which owns the loan account, the GL, every accrual, every NPA classification, and every EOD/BOD batch. The other services orbit it.

## Who uses it

- **Loan officers / field agents** — onboarding, KYC, application capture (LOS via webapp + android)
- **Credit underwriters / branch managers** — review, approval, deviation handling
- **Customer service / collections** — repayment processing, PTP, reschedule, foreclosure
- **Operations / RBH / RM** — task assignment, escalation, supervisory review
- **Finance teams** — GL, trial balance, manual JE
- **Compliance / auditors** — RBI ADF, UAM, audit trail, reporting
- **Tenant admins** — master data, role/permission, product configuration

## The 17 services

```
                                     ┌──────────────────┐
        web / android                 │   webapp (NG20)  │
        ─────────────►                └──────────┬───────┘
                                                 │
                                       ┌─────────▼─────────┐
                                       │   api-gateway      │  authn, authz check, STAN dedup,
                                       │  (sessions, STAN)  │  rate-limit, callback handling
                                       └────────┬──┬──┬──┬──┘
                                                │  │  │  │
                ┌───────────────────────────────┘  │  │  └──────────────────────────────────┐
                │              ┌───────────────────┘  └──────────────────┐                  │
                ▼              ▼                                         ▼                  ▼
         ┌────────────┐  ┌────────────┐  ┌──────────────┐  ┌─────────────────────┐  ┌────────────────┐
         │ novopay-   │  │  actor     │  │ accounting   │  │   payments (LCS)     │  │   approval     │
         │  mfi-los   │  │  (CRM)     │  │  v2 (LMS)    │  │                     │  │ (maker-checker)│
         │            │  │            │  │              │  │                     │  │                │
         │ 471 reqs   │  │ 29 XMLs    │  │ 9 XMLs        │  │ 4 XMLs              │  │ 2 XMLs         │
         │ in 1 XML   │  │ ~33k lines │  │ ~340 reqs    │  │ ~258 reqs           │  │ ~14 reqs       │
         └─────┬──────┘  └─────┬──────┘  └──┬───────┬───┘  └─────────┬───────────┘  └────────┬───────┘
               │               │            │       │                │                       │
               │               │            │       │                │                       │
               │ Kafka         │            │ Kafka │ HTTP            │                       │
               │ disburse_loan_api_<tenant> │ los_lms_disbursement_sync                       │
               ├───────────────────────────►│       │                │                       │
               │                            │ ◄─────┘                │                       │
               │                            │                        │                       │
               │                            │ HTTP collection-       │                       │
               │                            │ LoanRepayment          │                       │
               │                            │ ◄──────────────────────┘                       │
               │                            │                                                │
               │                            │ HTTP submitApplication                          │
               │                            ├──────────────────────────────────────────────► │
               │                            │                                                │
       ┌───────┴───────┐  ┌────────────┐  ┌─┴──────────┐  ┌────────────────────┐     ┌───────┴───────┐
       │   batch       │  │  task       │  │  audit       │  │   notifications     │     │ masterdata mgmt│
       │ (scheduler +  │  │ (operator   │  │ (req/resp +  │  │  (sms/email/fcm/   │     │ (code masters, │
       │  bulk upload) │  │  TAT/escal.)│  │  ES audit)   │  │   otp templates)   │     │  Redis cache)  │
       │ 22 reqs       │  │ ~60 reqs    │  │ 7 reqs       │  │ 13 reqs            │     │ 22 reqs        │
       └───────────────┘  └────────────┘  └──────────────┘  └────────────────────┘     └────────────────┘

      ┌───────────────┐  ┌──────────────────┐  ┌───────────────────┐  ┌────────────────────┐
      │     dms       │  │  authorization   │  │   initial-setup    │  │  trustt-platform-  │
      │ (FS / S3,    │  │ (roles / perms / │  │ (Flyway runner —   │  │     reporting      │
      │  verifyDocs)  │  │  usecase model)  │  │  not a service)    │  │ (RBI ADF, UAM,    │
      │ 6 reqs        │  │ ~40 reqs         │  │                    │  │  Posidex, MIS)    │
      └───────────────┘  └──────────────────┘  └────────────────────┘  └────────────────────┘

                                ┌──────────────────────────────────────────┐
                                │       novopay-platform-lib              │
                                │ infra-platform / -navigation / -cache / │
                                │ -kafka / -batch / -masterdata / -audit /│
                                │ -api-client / -tenant / -service-gateway│
                                │ (every service depends on this)         │
                                └──────────────────────────────────────────┘
```

Per-service brain docs: [`../services/`](../services/).

## What's special about this platform

1. **Orchestration is data, not code.** Every service has `deploy/application/orchestration/*.xml` declaring `<Request name="…">` → `<Validator>` / `<Processor>` / `<Control>` / `<API>` chains. The `infra-navigation` lib (`OrchestrationXMLParser` + `ServiceOrchestrator`) runs them. To find the API, grep the XML — not the Java.

2. **The contract between batch and accounting is a string.** `BatchJob.name` in the batch service must equal `<Request name="…">` in accounting. A renamed Request silently 404s.

3. **Maker-checker is a meta-pattern.** Every `createOrUpdate*` and `delete*` in accounting can be gated by `${maker_checker_enabled}`. When on, the same Request fires twice — once with `function_code=DEFAULT` (maker → goes to approval), once with `function_code=APPROVE` (checker → executes). The approval service is content-agnostic.

4. **SHG/JLG = parent loan + N children.** Children are *not* created inline; they're queued in `loan_account_events_queue` and replayed by `childLoanEventProcessingBatchJob`. See [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md).

5. **Disbursement is asynchronous.** LOS publishes a Kafka event; accounting consumes it; the loan moves through a 9-stage `function_sub_code` state machine; result event posted back to LOS.

6. **Every GL hit funnels through `postTransaction`.** That Request runs `ExecuteTransactionRulesProcessor`, which resolves placeholders → internal accounts → GL via the per-product `transaction_accounting_rule` rows. See [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md).

7. **Master data lives in masterdata-management** but every consumer caches in Redis (DB 1). Cache eviction discipline is critical.

8. **Multinode batch coordination is in-memory only** — no leader election in the batch service. Documented as HIGH RISK ([`../platform/multinode-batch.md`](../platform/multinode-batch.md)).

## Branch this brain covers

`mfi_integration_v3.2.8.4.1` — verified across all 17 darpan checkouts ([`../workspace-state.md`](../workspace-state.md)).
