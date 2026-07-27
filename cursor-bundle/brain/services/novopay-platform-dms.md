# `novopay-platform-dms` — Document store with dual storage backend

> File system **or** S3, switchable per tenant via config. Owns document upload/download/verify/validate/merge plus the `verifyDocuments` Request that disbursement gates on. **No Kafka, no Redis cache.**

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.dms` |
| DB schema | (single cluster, unqualified) — primary tables `document_master`, `file_master`, `document_tags`, `sequence_generator` |
| Repo | [`novopay-platform-dms/`](../../novopay-platform-dms/) |
| Service CLAUDE.md | [`trustt-platform-dms/CLAUDE.md`](../../trustt-platform-dms/CLAUDE.md) |

## API surface — `ServiceOrchestrationXML.xml` (6 Requests)

`uploadDocument`, `downloadDocument`, `getDocumentDetails`, `verifyDocuments`, `validateDocuments`, `mergeDocuments`.

## How storage routing works

Config key: `dms.service.document.storage.location` ∈ `FILE_SYSTEM` | `S3_SYSTEM`.

Processors branch on the storage type at runtime:
- `FILE_SYSTEM` → local/network folder via `GetStorageLocationProcessor`
- `S3_SYSTEM` → AWS S3 SDK via `UploadDocumentToAWSProcessor`

**No HTTP outbound** other than AWS S3. Read-only access to masterdata for config.

## Upload modes

| Mode (`function_sub_code`) | Behaviour |
|---|---|
| `CREATE` | Generate new document code, new document_master + file_master rows |
| `UPDATE` | Existing `document_code` required; optional file numbers validated |
| `REPORT_UPLOAD` | Large reports streamed directly to S3 |

## `verifyDocuments`

Used by accounting `disburseLoan` (and other LOS flows) to gate execution on KYC + agreement + NACH-mandate verification. Sets `document_master.isVerified = true` for a batch of document codes.

[`VerifyDocumentsProcessor.java`](../../trustt-platform-dms/src/main/java/in/novopay/dms/processor/VerifyDocumentsProcessor.java)

## Document taxonomy

**No formal type taxonomy in code.** Documents are identified by `code` (auto-generated) + optional `version`. Business taxonomy (KYC vs loan-doc vs e-sign vs report) is owned by callers.

## Known gotchas

1. **Storage backend duality** — config + environment must align (FS path exists / S3 bucket + creds present).
2. **Upload mode validators differ by `function_sub_code`** — debugging starts with which mode was actually used.
3. **Merge flow is internal-only** — `mergeDocuments` calls back into DMS APIs, never out.
