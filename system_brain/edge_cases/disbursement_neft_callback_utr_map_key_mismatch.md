# NEFT Callback UTR Map Key Mismatch (Array Payload Branch)

## Scope
- Processor: `DoGenericSyncSTPBankNeftCallBackProcessor`.
- Path: NEFT callback parse (`parseNEFCallback`) when callback payment list is array-shaped.

## Verified behavior (2026-04-22)
- Array branch stores UTR map as:
  - `utrMap.put(paymentObject.get(REFERENCENO).toString(), utrNumber)`
- Callback processing later fetches with external reference (`paymentrefno`):
  - `utrMap.get(externalReferenceNumber)`

## Why it matters
- For successful callbacks, UTR lookup can return null in array branch even when callback includes reference number.
- Stage progression may happen without UTR persistence on loan/queue rows.

## Evidence file
- `novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/disbursement/processor/DoGenericSyncSTPBankNeftCallBackProcessor.java`

## Risk
- Medium (traceability + downstream reconciliation quality).

