# 01 · Accounting — Overview

## Service coordinates

| Field | Value |
|-------|-------|
| Service name | `novopay-platform-accounting-v2` |
| Java root package | `in.novopay.accounting.*` |
| DB schema | `mfi_accounting` |
| Error-code prefix | `NOT-` (e.g. `NOT-IAD-001`, `NOT-GLS-002`) |
| Orchestration root | `deploy/application/orchestration/` |
| Kafka consumer | `in.novopay.accounting.consumers.LmsMessageBrokerConsumer` |
| Redis DB index | `RedisDBConfig.ACCOUNTING` (used for in-flight dedup) |

## Orchestration XMLs

The service splits its API surface across nine XMLs. All nine are loaded by `OrchestrationXMLParser` at startup and merged into a single `<Request name=…>` namespace that the gateway/internal API client routes against.

| XML | Lines | Domain |
|-----|------:|--------|
| `ServiceOrchestrationXML.xml` | 9 715 | GL, internal accounts, tax, interest setup, base interest, asset criteria, holiday, working day, savings product, server clock, notifications, mandates |
| `loans_orc.xml` | 6 490 | Loan account CRUD, disbursement, repayment, prepayment, foreclosure, accrual, billing, restructuring, reschedule, write-off, advance repayment, recurring batch |
| `mfi_orc.xml` | 2 875 | EOD/BOD (`runEODJobs`, `runBODJobs`), trial balance & zeroisation, foreclosure-charge bulk, manual JE bulk, NOC, dispatch, sec-NPA, derived fields, CASA extracts, Finsall repayment, bank-service retry, NEFT callback |
| `product_transaction_accounting_definition_orc.xml` | 1 829 | Transaction catalogue, placeholder masters, accounting rules, asset classification |
| `insurance_orc.xml` | 779 | Insurance product master + premium calculation matrix |
| `group_mfi_orc.xml` | 687 | Child loan booking, repayment, restructuring, reopening, foreclosure, transaction reversal, part prepayment, disbursement-cancellation |
| `product_transaction_orc.xml` | 641 | `postTransaction`, `getAccountBalances`, account statement, manual JE post/reverse, GL transfer, GL zeroisation, portfolio transfer |
| `loans_insurance_orc.xml` | 240 | Inbound/outbound disbursement & death-foreclosure insurance jobs (HDFC Life, HDFC Ergo, Bajaj Ergo) |
| `loans_notification.xml` | 14 | Loan notification stubs |

Total Request endpoints: **~340** (matches the prior `~348` count in the existing aitdp-docs).

## Package map (top-level only)

```
in.novopay.accounting
├── account                 — savings / loans / common entities, balance, statement
├── accountingrules         — accounting-rule master (DR/CR templates per transaction)
├── assetclassificationmaster
├── assetcriteriamaster     — asset criteria + slabs (NPA classification rules)
├── baseinterestrate        — base rate slabs by date
├── batch                   — disbursement + disbursement-cancellation Spring Batch jobs
├── batchnew                — 30+ Spring Batch job packages (see 03-batch-dependency.md)
├── clock                   — server-clock master, working-day overrides
├── common                  — constants, utils, validators
├── config                  — Spring config, Kafka, Redis, scheduler wiring
├── consumers               — LmsMessageBrokerConsumer (Kafka)
├── currencymaster          — currency / FX placeholder
├── custom                  — tenant-specific custom processors
├── enach                   — eNACH presentation/representation file generation
├── excessamount            — excess-amount refund flows
├── filewriter              — bulk-file output writers (NOC, Finsall, dispatch)
├── generalledger           — GL master + child GL
├── holiday                 — holiday calendar
├── insurance               — insurance product, premium matrix, validate
├── interestsetup           — interest-setup master, slabs, processors
├── internalaccount         — internal account instances
├── internalaccountdefinition — internal-account templates
├── loan                    — interest, lrs (loan repayment schedule), part-prepayment, etc.
├── pricing                 — price master, price setup, stamp duty
├── product                 — generic product registry
├── productscheme           — scheme catalogue
├── portfoliovalidation     — LMS portfolio transfer validation
├── reversal                — transaction reversal
├── service                 — `AccountingKafkaProducer` and shared services
├── standinginstructions    — SI registration + retry
├── taxcomponent / taxgroup — tax masters + GL mapping
├── transaction             — `postTransaction`, manual JE, GL transfer
├── transactioncatalogue    — txn-catalogue master + placeholders
└── validator               — orchestration validator beans
```

## `batchnew` sub-packages (the real "accounting batch")

Each leaf is a Spring Batch job, typically with `*BatchConfigService`, `*BatchProcessor`, `*ItemReader`, `*ItemProcessor`, `*ItemWriter`, `*Service`, `*Vo`, `*FailureEntityMapper`. Job names match the orchestration `<Request name="…">` so the batch service can call them by name.

```
batchnew
├── bankservicecallretry
├── bulkassetcriteriaupdate
├── bulkmanualjournalentry
├── bulknoc
├── bulkpreforeclosurechargeupdate
├── bulkrepayment           ├── bulkfiletosgfinsallrepaymentjob
│                           └── bulksgtofinsallrepaymentjob
├── bulktransactionreversal
├── casabalanceupdate
├── childloaneventprocessingbatchjob
├── deleteaccountingtaskusingcode
├── derivedfields
├── enach
├── insurancegeneration
├── insurancerecovery
├── interest                ├── interestaccrualbooking
│                           └── interestaccrualcalculation
├── loanaccountbilling
├── loanaccountclosure
├── loanaccountservicingdocumentevents
├── loanadvancerepayment
├── loanrecurringpaymentbatchapi
├── notifications
├── npa                     ├── primary
│                           └── secondary
├── penal
├── refund
├── standinginstruction
└── trialbalance
```

## Domain entities (representative)

GL & accounts: `GeneralLedgerEntity`, `ChildGeneralLedgerEntity`, `InternalAccountDefinitionEntity`, `InternalAccountEntity`, `AccountEntity`, `AccountBalanceEntity`, `AccountInterestDetailsEntity`.

Loans: `LoanAccountEntity` (with `LoanStatus` enum incl. `ACTIVE`/`LOCK`), `LoanInstallmentDetailsEntity`, `LoanDueDetailsEntity`, `InterestAccrualDetailsEntity`, `LoanAccountPartPrepaymentDetailsEntity`.

Tax: `TaxComponentEntity`, `TaxGroupEntity`, `TaxGroupTaxComponentMappingEntity`.

Interest setup: `InterestSetupEntity`, `InterestSetupAmountSlabEntity`, `BaseInterestMaster`, `BaseInterestSlab`, `BaseInterestDateSlab`.

Asset / NPA: `AssetClassificationMasterEntity`, `AssetCriteriaMasterEntity`, `AssetCriteriaGroupEntity`, `AssetCriteriaSlabsEntity`.

Insurance: `InsuranceProductEntity`, `InsuranceCalculationMatrixSlabDetailsEntity`, `InsuredTypeCalculationMatrixDetailsEntity`, plus `*StagingDetailsEntity` for inbound/outbound files.

eNACH: `EnachPresentationDetailsEntity`, `EnachPresentationLoanAccountDetailsEntity`, `EnachRepresentationDetailsEntity`, `EnachRepresentationLoanAccountDetailsEntity`.

Bulk file staging: `FileStagingDispatchDetails`, `FileStagingFinsallRepayment`, `FileStagingManualHoldMarking`, `FileStagingPostDisbursementInsurance`, `FileStagingSecNpaReverseFeedFile`.

## Error-code conventions

Errors are grouped by sub-module code:

| Sub-code | Sub-module |
|----------|------------|
| IAD | Internal Account Definition |
| GLS | General Ledger |
| TXC | Tax Component |
| TXG | Tax Group |
| AIM / ACM | Asset Criteria / Classification Master |
| INT | Interest Setup |
| LON | Loan Account |
| FOR | Foreclosure |
| INS | Insurance |
| ENC | eNACH |
| NPA | NPA / Asset Criteria Job |

Within an XML, validators emit numeric codes (e.g. `130001`–`132018` for GL create) which the framework wraps with the `NOT-…` prefix when surfaced to clients.

## Maker-checker switch

Every CRUD orchestration is wrapped in `<Control method="regExp" pattern="${maker_checker_enabled}" condition="=" value="0|1">`. When enabled, the processor pipeline ends with `accounting_submitApplication` (calls the approval service) and a `deleteDraftProcessor`; when disabled, it commits directly via the domain `*Processor`. See `02-architecture.md` for the full flow.
