# `trustt-platform-reporting` — EOD + scheduled reports

> Java Spring Boot reporting microservice. Generates regulatory reports (RBI ADF), operational extracts (UAM, Posidex), loan/collection MIS, performance metrics, and KYC/CIC compliance reports. Scheduled by the batch service or triggered on demand. Uploads completed reports to DMS; logs to Elasticsearch.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay` (note: short top-level for legacy reasons) |
| DB | PostgreSQL/YugabyteDB at `localhost:5433/yugabyte` (per dev `application.properties`) |
| Server context path | `/reporting`, port `8888` |
| Repo | [`trustt-platform-reporting/`](../../trustt-platform-reporting/) |
| Service .cursorrules | [`(.cursorrules removed — use service README / AGENTS.md)`](../../(.cursorrules removed — use service README / AGENTS.md)) |

## Scale

- **172 report processors**
- **70+ report types**
- **150+ Requests** in `ServiceOrchestrationXML.xml` (972 lines)

## Report categories

| Category | Examples |
|---|---|
| RBI ADF extracts | `generateRBIAdfBankDetailsExtractJob`, customer details, GL details, legal security, account, interest income |
| UAM (User Access Mgmt) | `generateUAMPopulationExtractJob`, role-right extracts, login-logout extracts |
| Loan MIS | loan card fact sheet, repayment schedules, demand lists, disbursement advice |
| Posidex | daily / monthly extracts (credit bureau data, async to Kafka) |
| Performance metrics | `spanSoJob`, RBH/RM/BRH productivity audits, credit group/customer metrics |
| Compliance | CKYC, NRLM, CIC, insurance reports |
| Collections | demand lists, DPD buckets, collection efficiency |

## How EOD reports are triggered

Accounting fires `generatePostEODReports` at the end of `runEODJobs`. That cascades through `BatchJob` → DirectJobExecutor → calls into reporting service Request `generateReport` (or per-report `generate*Job`).

`generateReport` Request branches on `report_code` via Control regex. Each branch dispatches to a specific report processor (e.g. `generateRBIAdfBankDetailsExtractJob`).

## Storage / serving

- **Templates** — `deploy/application/templates/`
- **Output** — `deploy/application/templates/output/` (file system)
- **DMS upload** — finished reports POSTed to `https://<env>/api-gateway/document/v1/uploadDocument`
- **Audit / search** — Elasticsearch at `172.31.2.221:6200` (dev)

## Kafka

Producers:
- `AuditDataKafkaProducer` — pushes Posidex extract / audit data to:
  - `POSIDEX_ACTOR_INBOUND_TOPIC_NAME`
  - `POSIDEX_LOS_INBOUND_TOPIC_NAME`

Consumed by actor / LOS Posidex pipelines.

## When you'll touch this

- A new regulatory or operational report → add a `<Request name="generate*Job">` + a processor implementing the extract; register in batch service if it's scheduled.
- A failing report → find the report processor (172 of them), check its data sources, validate template path + output path.
- Report not appearing in DMS → check the upload step; could be a DMS auth failure or storage backend mismatch.
