# 11 · Glossary — definitive cross-service vocabulary

> If a term in any doc here confuses you, look it up here. Acronyms first, concepts second. Authoritative.

## Acronyms

| Term | Expansion / meaning |
|---|---|
| **LMS** | Loan Management System — the **accounting** service is the LMS |
| **LOS** | Loan Origination System — `novopay-mfi-los` |
| **LCS** | Loan Collection System — `novopay-platform-payments` |
| **MFI** | Microfinance Institution |
| **SHG** | Self-Help Group — informal women's savings/lending group; one parent loan + N child loans |
| **JLG** | Joint Liability Group — joint-borrower group with mutual guarantee |
| **DPD** | Days Past Due |
| **NPA** | Non-Performing Asset (RBI categories: SMA-0/1/2, Substandard, Doubtful, Loss) |
| **EMI** | Equated Monthly Installment |
| **EOD / BOD** | End-of-Day / Beginning-of-Day batch cycles |
| **GL** | General Ledger |
| **JE** | Journal Entry |
| **TB** | Trial Balance |
| **STAN** | System Trace Audit Number — gateway per-request unique id, for dedup/replay |
| **EC** | Execution Context — the per-Request shared map between processors |
| **SOF** | Service Orchestration Framework — the lib's orchestration runtime |
| **NEFT** | National Electronic Funds Transfer (Indian bank transfer rail) |
| **NACH** | National Automated Clearing House (mandate-based debit rail) |
| **eNACH** | Electronic NACH (digital mandate flow) |
| **SI** | Standing Instruction (mandate presentation flows) |
| **FCM** | Firebase Cloud Messaging (push notifications) |
| **OTP** | One-Time Password |
| **CKYC** | Central KYC registry |
| **eKYC** | Electronic KYC (Aadhaar-driven) |
| **PAN** | Permanent Account Number (Indian tax ID) |
| **VTC** | Village/Town/City — geography level in actor's hierarchy |
| **FLCC** | Financial Literacy & Credit Counselling (group readiness check) |
| **BET** | Borrower Engagement Tool (questionnaire stage in LOS) |
| **DDE** | Detailed Data Entry (LOS stage) |
| **QDE** | Quick Data Entry (LOS stage) |
| **HHIE** | Household Income & Expense (LOS stage) |
| **GFM** | Group Formation Module (LOS stage; SHG/JLG only) |
| **CUWRTR** | Credit Underwriting (LOS stage) |
| **CPDC** | Credit Policy Document Check (LOS stage; pre-disbursement) |
| **CM / BM / RM / RBH / SO** | Credit Manager / Branch Manager / Relationship Manager / Regional Branch Head / Sales Officer (operator roles) |
| **PTP** | Promise to Pay (collection follow-up) |
| **PSL** | Priority Sector Lending (RBI category) |
| **APY** | Atal Pension Yojana (govt scheme) |
| **NRLM** | National Rural Livelihoods Mission |
| **CIC** | Credit Information Company (bureau) |
| **RBH** | Regional Branch Head |
| **VRM** | Variable Risk Module (?) — used as an actor cluster name |
| **TAT** | Turn-Around Time (task deadline) |
| **NOC** | No Objection Certificate (issued post-closure) |
| **MIS** | Management Information System (reports) |
| **ADF** | Automatic Data Flow (RBI regulatory submission) |
| **UAM** | User Access Management |
| **CASA** | Current Account Savings Account |

## Concepts

### Account vs loan_account
- `account` is the generic table (savings + loans), with `AccountStatus` (5 values: ACTIVE, INACTIVE, CLOSED, CANCELLED, APPROVED).
- `loan_account` is a JOINED inheritance specialisation, with `LoanStatus` (16 values, see [`../accounting/07-loan-account-lifecycle.md`](../accounting/07-loan-account-lifecycle.md)).
- Always read `loan_status` for loan state, not `account.status`.

### Parent vs child loan (SHG/JLG)
- **Parent loan_account** — represents the group's loan, holds aggregate disbursement + master schedule + GL postings.
- **Child loan_accounts** — one per group member, with `account.parent_account_id = parent.id` and `loan_account.fraction` for EMI share.
- Children created asynchronously via `loan_account_events_queue` + `childLoanEventProcessingBatchJob`.

### Maker / Checker
- **Maker** — operator who initiates a state change. Goes through `submitApplication` → creates a draft.
- **Checker** — operator who reviews. `approveApplication` re-fires the original Request with `function_code=APPROVE`.
- Toggle is `${maker_checker_enabled}` per Request, read from tenant config.

### Function code / Function sub code
- `function_code` — Request-level branch (e.g. `DEFAULT`, `APPROVE`, `RESUBMIT`, `BATCH`). Used by maker-checker, batch invocations, and tenant-specific behaviours.
- `function_sub_code` — sub-branch within a Request. Heaviest use: `disburseLoan`'s 9-stage state machine.

### Run mode
- `run_mode` — `TRIAL` (compute, return, no DB write) or `REAL` (commit). `postTransaction` honours this.

### Op code
- `op_code` — operation type. `RESTART` is forced by `DirectJobExecutor` to allow a batch job to re-run from where it left off.

### Transaction catalogue
- A *named transaction* (e.g. `LOAN_DISB_PRIN`, `LOAN_REP_INT`). One per business operation that hits the GL. Each has N `transaction_accounting_rule` rows defining the legs.

### Placeholder
- A *symbolic account name* (e.g. `BANK_AC`, `LOAN_PRINCIPAL_AC`). Resolved per (product, transaction_catalogue) into an `internal_account` instance + GL code. See [`../accounting/08-gl-posting-engine.md`](../accounting/08-gl-posting-engine.md).

### Internal account
- A physical office-scoped instance of an `internal_account_definition`. The actual ledger account that's debited/credited.

### Use case
- A logical action (e.g. `GENL-LEDG-UC001`). Master in actor; permission-bound via authorization; mapped to API Requests via gateway's `api_usecase_mapping`.

### `<Request>`
- The orchestration XML's top-level element. Defines a callable API: validators, processor chain, control branches, `<API>` calls, transaction-management flag, undo list.

### `<API>`
- An element inside a Request's processor list that calls another service's Request via `NovopayInternalAPIClient`.

### Execution Context
- The `Map<String, Object>`-like object the lib passes through every processor. Each processor reads inputs and writes outputs into it. Per-Request EC contracts: [`../platform/execution-context-contracts.md`](../platform/execution-context-contracts.md).

### Spring Batch meta-tables
- `BATCH_JOB_INSTANCE`, `BATCH_JOB_EXECUTION`, `BATCH_STEP_EXECUTION`, `BATCH_STEP_EXECUTION_CONTEXT`. Owned by Spring Batch, live in the target service's datasource. The batch service polls these (over HTTP) for status.

### `batch_job` (registry)
- Row in `mfi_batch.batch_job` mapping a job name to its target Request (target service decided by routing). NOT the same as `BATCH_JOB_INSTANCE`.

### Asset criteria
- Master that maps DPD ranges to an asset classification slab (e.g. DPD 0-30 = STD, 31-60 = SMA-1, 91+ = NPA-Substandard). Per-product binding via `loan_product_asset_criteria` which also encodes the **appropriation precedence** (4 component slots) and **liquidation order** (`LIQ_INSTL` / `LIQ_COMP` / `LIQ_INSTL_CHRG_COMP`).

### Disbursement status
- Column on `loan_account`, distinct from `loan_status`. Tracks bank-side progression: `BANK_SUCCESS`, `LOAN_BOOKED`, `REINITIATE_BANK`, `NEFT_STAGE_*`, `PARENT_SUCCESS`, `CHILD_SUCCESS`, `COMPLETED`. Drives the `disburseLoan` state machine.

### Excess amount / suspense
- After a repayment, leftover money (over total due) goes into `loan_account_payments_details.excess_amount` for auto-clearance against next dues.
- For NPA loans, the interest portion of a payment is shunted to the **suspense GL** instead of interest income.

### Liquidation order
- Within a repayment, how due rows are sorted before appropriation:
  - `LIQ_INSTL` — by installment date, then by component
  - `LIQ_COMP` — by component, then by date
  - `LIQ_INSTL_CHRG_COMP` — installments by date, then charges by component
- Per product, in `loan_product_asset_criteria.liquidation_order`.

### Component types
- `PRIN` (principal), `INT` (interest), `PINT` (penal interest), `FEE` (fee/charge). Codes in `AccountingConstants.java` lines 42-45.

### Tenant code
- Short identifier per tenant: `mfi`, `idfcp`, `product`, `waas`, `bp`, `fk`, `nl`. Resolved at gateway, propagated via `ThreadLocalContext`.

### Idempotency
- Three layers:
  1. **Gateway STAN dedup** — `request_stan_log` rejects duplicates.
  2. **Audit replay** — `getApiResponseByStan` returns the prior response.
  3. **Posting dedup** — `client_reference_number` on `postTransaction` rejects duplicate transaction headers.

### Maker-checker target API replay
- When `approveApplication` fires, it re-invokes the original Request with `function_code=APPROVE`. The target Request must skip the "submit for approval" branch and execute the actual mutation. Idempotency in this branch is critical.

---

## Modules, infra-libraries, error-code ranges & status enums
_(merged from the former docs/glossary.md — the reference-table half of the vocabulary)_


## Modules
- **Accounting-v2**: Loan accounts, GL, disbursements, repayments, charges, standing instructions, NPA, trial balance
- **MFI-LOS**: Loan Origination System — loan application lifecycle, group management, disbursement initiation
- **Actor**: Employee, office, customer, branch management; MapMyIndia integration
- **Payments**: Collections, challan, receipts, bulk collection, allocation
- **Task**: Task creation/assignment for collections and operations
- **Approval**: Maker-checker approval workflow
- **Authorization**: User authentication and authorization
- **Batch**: Spring Batch + Kafka for scheduled/bulk operations (eNACH, NPA, trial balance, refund)
- **Notifications**: SMS, email, FCM push notifications
- **API Gateway**: Request routing, rate limiting, authentication proxy
- **Reporting**: Reports and data extracts (trustt-platform-reporting)
- **DMS**: Document management
- **Masterdata**: Master data configuration (products, schemes, codes)

## Infra Libraries (`novopay-platform-lib/`)
- **infra-platform**: AbstractProcessor, ExecutionContext, validators, NovopayFatalException
- **infra-navigation**: Orchestration engine — reads XML, executes flow, manages transactions
- **infra-jtf**: JSON Template Framework — builds bank request/response from templates
- **infra-message-broker**: Kafka consumer/producer infrastructure
- **infra-batch**: Spring Batch + Kafka integration
- **infra-cache / infra-cache-gateway**: Redis caching
- **infra-http-client**: HTTP client for external calls
- **infra-transaction-hdfc / indusind / ccavenue**: Bank-specific integration adapters

## Domain Terms
- **VTC**: Village/Town/City — location identifier (`vtc_id`)
- **LAN**: Loan Account Number — unique loan identifier
- **SHG**: Self Help Group — group of borrowers
- **MFI**: Microfinance Institution
- **KFS**: Key Fact Statement — disclosure document showing charges/terms
- **NPA**: Non-Performing Asset — loan classification when payments are overdue
- **eNACH**: Electronic National Automated Clearing House — auto-debit mandate
- **NEFT**: National Electronic Funds Transfer — bank transfer mechanism
- **IMPS**: Immediate Payment Service — real-time bank transfer
- **NEF**: NEFT fund-transfer leg (e.g. HDFC ST_NEF — stage 1 in typical v2 two-stage disbursement)
- **NEI**: NEFT inquiry / second-stage leg (e.g. ST_NEI — follows NEF in v2; exact naming varies by partner template)

## Technical Terms
- **ExecutionContext**: Mutable map-like object that carries data between processors in a flow
- **Processor**: Component extending AbstractProcessor, implementing `process(ExecutionContext)`
- **Orchestration XML**: Declarative flow definition (validators → processors → controls → API calls)
- **JTF Template**: JSON structure that maps ExecutionContext keys to bank API request/response fields
- **WebClient Decorator**: `WebClientServiceExecutorDecorator` — makes bank API calls using templates
- **Partner Discovery**: `AbstractPartnerDiscoveryService` — selects bank implementation by `partner_code`
- **STAN**: System Trace Audit Number — unique request identifier
- **Soft Delete**: `is_deleted` flag; never physically delete records
- **Maker-Checker**: Two-step approval (maker creates, checker approves/rejects)
- **Function Code**: Operation type: DEFAULT (direct), APPROVE, REJECT
- **Function Sub Code**: Sub-operation: CREATE, UPDATE, DELETE, LIST, DETAILS

## Error Code Ranges
- **130001–130099**: Mandatory field validation errors
- **132001–132099**: Pattern validation errors
- **134001–134999**: Business logic errors (e.g. 134139 = entity not found)
- **30000–30099**: Success response codes
- **SERVICE-XXXX**: Service-prefixed error codes (e.g. LOS-5095, ACCT-0028)

## Status Values
- **Loan Account**: PENDING, PRE_DISBURSEMENT, ACTIVE, CLOSED, NPA, WRITTEN_OFF
- **Disbursement**: INITIATED, NEFT_STAGE_1_PENDING, NEFT_STAGE_2_PENDING, ACTIVE, FAILED, INQUIRY_PENDING
- **Collection**: PENDING, ALLOCATED, COLLECTED, FAILED, REVERSED