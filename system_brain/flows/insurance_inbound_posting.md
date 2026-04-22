# Insurance Inbound Posting Paths (accounting-v2; code-verified)

This doc focuses on the end-to-end chain starting from:
- `runInbound*InsuranceJob` (folder scan)
- `inbound*InsuranceJob` (staging load)
- the subsequent batch/job that performs any `postTransaction` (if applicable)

## 1) Death Foreclosure Insurance

### A) Trigger + internal API fanout (folder scan)
- Orchestration request: `runInboundDeathForeclosureInsuranceJob` (processor `RunInboundDeathForeclosureInsuranceJobProcessor`)
- Batch wiring (code-verified):
- `runInboundDeathForeclosureInsuranceJob` uses `RunInboundJobBatchConfigService` which runs `RunInboundJobTasklet`; `RunInboundJobTasklet` scans inbound folder and calls internal API `inboundDeathForeclosureInsuranceJob` per file with `executionContext.put("file_original_name", fileName)`.

### B) Inbound file -> staging load
- Orchestration request: `inboundDeathForeclosureInsuranceJob` (processor `InboundDeathForeclosureInsuranceJobProcessor`)
- Processor behavior (code-verified):
- sets `upload_type = DEATH_FORECLOSURE_INSURANCE` and calls `parallelJob.runInboundFileUploadJob(jobName, operationType, overrideParams)`.
- Batch wiring (code-verified):
- `inboundDeathForeclosureInsuranceJob` uses `InboundBatchConfigService` (inbound header + file-to-staging + inbound writer + inbound tasklet).

### C) Staging -> ledger posting (`postTransaction`)
- Orchestration request: `deathForeclosureInsuranceJob` (processor `DeathForeclosureInsuranceJobProcessor`)
- Batch wiring (code-verified):
- batch job `deathForeclosureInsuranceJob` uses `DeathForeclosureInsuranceWriter` (from `DeathForeclosureInsuranceConfigService`).
- Posting calls (code-verified) inside `DeathForeclosureInsuranceWriter`:
- calls internal API `postTransaction` with `transaction_type = DEATH_FORECLOSURE`, then later calls `postTransaction` with `transaction_type = RSCH_DEATH_FORECLOSURE`.

## 2) Disbursement Cancellation Insurance (posting cancellation leg + tax reversal)

### A) Trigger + internal API fanout (folder scan)
- Orchestration request: `runInboundDisbursementCancellation*InsuranceJob` (provider-specific variants)
- Those `runInbound*` requests use `RunInboundJobBatchConfigService` and `RunInboundJobTasklet`:
- scan inbound folder and call internal API `inboundDisbursementCancellation<Provider>...Job` per file (with `file_original_name`).

### B) Inbound file -> staging load
- Orchestration request: `inboundDisbursementCancellation<Provider>...Job` (processor `InboundDisbursementCancellationInsuranceJobProcessor`)
- Processor behavior (code-verified):
- computes `upload_type` via `InsuranceBatchUtil.constructInsuranceCancellationUploadType(insuranceProviderCode, policyType)` and calls `parallelJob.runInboundFileUploadJob(jobName, operationType, overrideParams)`.

### C) Staging -> ledger posting (`postTransaction`) + cancellation tax reversal
- Orchestration request: `bulkSGToDisbursementCancellationJob`
- Processor: `BulkSGToDisbursementCancellationJobProcessor`
- Batch/job configuration (code-verified):
- `SGToDisbursementCancellationBatchConfigService` defines `JOB_NAME = bulkSGToDisbursementCancellationJob`, and the writer is `SGToDisbursementCancellationIWriter`.
- Posting + tax reversal (code-verified) inside `SGToDisbursementCancellationIWriter#doDisbursementCancellation(...)`:
- calls internal API `postTransaction` with `transaction_type = LOAN_DISB_CNCL`, `transaction_sub_type = CASH`, and `amount = total_cancellation_amount`, then calls `initiateCancellationTaxReversalProcessor.execute(executionContext)` (`InitiateCancellationTaxReversalProcessor` does external GST reversal + reversal flag update).

## 3) Post-Disbursement Insurance (no ledger `postTransaction` in this chain)

### A) Trigger + inbound staging load
- Orchestration request:
- `runInboundDisbursement<Provider>...InsuranceJob` -> `RunInboundDisbursementInsuranceJobProcessor` (folder scan) and `inboundDisbursement<Provider>...InsuranceJob` -> `InboundDisbursementInsuranceJobProcessor` (staging load).

### B) Staging -> insurance status update + provider file generation
- Orchestration request: `bulkSGToPostDisbursementInsuranceUpdateJob`
- Processor: `BulkSGToPostDisbursementInsuranceUpdateJobProcessor`
- Batch/job config (code-verified):
- `SGToPostDisbursementInsuranceUpdateBatchConfigService` uses `SGToPostDisbursementInsuranceUpdateIWriter` plus `PostDisbursementInsuranceUpdateTasklet` and `PostDisbursementFileCreationTasklet`.
- Posting calls:
- this chain performs insurance status + file creation and does NOT call internal API `postTransaction` (no ledger movement in this specific pipeline).

