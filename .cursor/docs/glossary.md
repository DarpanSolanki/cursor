# Novopay Platform Glossary

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