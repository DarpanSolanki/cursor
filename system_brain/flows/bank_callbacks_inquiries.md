# Bank callbacks + inquiries (accounting-v2; disbursement-centric)

## STP/NEFT callback entrypoints (accounting-v2)
- Orchestration requests:
  - `doGenericSyncSTPBankNEFNeftCallBack` (callback_type = `ST_NEF`)
  - `doGenericSyncSTPBankNEINeftCallBack` (callback_type = `ST_NEI`)
- Processor:
  - `in.novopay.accounting.loan.disbursement.processor.DoGenericSyncSTPBankNeftCallBackProcessor#process(...)`

### What it parses (code-verified)
- `callback_type` controls which payload key is read:
  - `ST_NEF` → reads `paymentlist` (JSONObject)
  - `ST_NEI` → reads `inqlist` (JSONObject)

## Disbursement state + DB mutations (code-verified)
### Parent `loan_account` disbursement_status + fillers
- `loan_account.disbursement_status` set on success paths:
  - `ST_NEF` success: `NEFT_STAGE_1_SUCCESS`
  - `ST_NEI` success: `COMPLETED`
  - failure/DTFC-success handling: `DTFC_SUCCESS`
- Filler fields:
  - sets `filler1`/`filler2` with error/status text in failure paths

### `loan_disbursement_mode_details.utrNumber`
- On NEFT success paths, sets UTR into `LoanDisbursementModeDetailsEntity` and persists.

### Child loan events queue (`loan_account_events_queue`)
- Updates queue JSON `data`
- updates queue fillers and `event_status` to `COMPLETED`

## Bank inquiry + inquiry result persistence
- Processor:
  - `in.novopay.accounting.loan.disbursement.processor.CallBankAPIForDisbursementProcessor`
- Inquiry routing:
  - For NEFT stage 1 pending: constructs NEFT inquiry inputs with `NEFT_STAGE = "ST_NEF"` and calls NEFT inquiry partner discovery.
  - For MFT: calls generic transaction status inquiry.

### DB mutation confirmed in code
- inquiry success path writes `loan_disbursement_mode_details.utrNumber`
- bank call results create `ClientRequestResponseLogEntity` via `logBankCall(...)`

## Confidence / gaps
- High: parsed keys + confirmed DB mutation fields for callbacks and inquiry outcomes (from the processor code we traced).
- Medium/UNVERIFIED: whether every nested edge status maps identically across all NEFT variants; this doc focuses on confirmed mutation points.

