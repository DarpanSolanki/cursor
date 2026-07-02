# `novopay-platform-masterdata-management` — Code masters + configurations

> Pure read-mostly hub for code-value pairs (the system's enums-as-data) and configurations. **No Kafka, no outbound HTTP.** Heavy Redis cache (DB index 1).

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.masterdata` |
| DB schema | `mfi_masterdata` |
| Repo | [`novopay-platform-masterdata-management/`](../../novopay-platform-masterdata-management/) |
| Service CLAUDE.md | [`novopay-platform-masterdata-management/CLAUDE.md`](../../novopay-platform-masterdata-management/CLAUDE.md) |

## API surface — `ServiceOrchestrationXML.xml` (~22 Requests)

Top: `getDatatypeMaster`, `getCodeMasterListBasedOnGroup`, `getBranchList`, `getBankList`, `createOrUpdateConfiguration`, `getApyConfiguration`.

## Concepts

### dataType / dataSubType

Code masters are identified by a **(dataType, dataSubType)** pair, e.g. `(TAX_TYPE, DEFAULT)` or `(REPAYMENT_MODE, LOANS)`. Each maps to a list of code-value rows in `code_master_details`.

Entities:
- [`CodeMasterEntity.java`](../../novopay-platform-masterdata-management/src/main/java/in/novopay/masterdata/codemanagement/entity/CodeMasterEntity.java) — header
- `code_master_details` — values

### How services consume master data

There are two consumer patterns:

1. **`<Validator bean="masterDataValidator">`** in orchestration XML — declarative validation. Used heavily by accounting:
   ```
   <IParam fieldName="disbursement_mode" type="DISBURSEMENT_MODE" subType="LOANS" errorCode="132165"/>
   ```
2. **Programmatic via `MasterDataUtil.getBulkMasterDataMapping(...)`** — used inside processors when multiple datatypes are needed (e.g. `ExecuteTransactionRulesProcessor` pre-fetches `TAX_TYPE/DEFAULT`).

Both paths go through Redis cache first; cache miss → masterdata service.

### Datatypes referenced from accounting (representative)

`CURRENCY/ISO_CODES`, `GL_CATEGORY/DEFAULT`, `BAL_TYPE/DEFAULT`, `ALLOWED_TXN_TYPE/DEFAULT`, `GL_STATUS/DEFAULT`, `TAX_TYPE/DEFAULT`, `DISBURSEMENT_MODE/LOANS`, `REPAYMENT_MODE/LOANS`, plus per-master codes for IAD, INT, AIM, ACM, etc. Full list inside accounting orchestration XMLs (`<IParam type="…" subType="…">`).

## Caching

Redis DB index **1 (MASTER_DATA)**. Key pattern: `{dataType}_{dataSubType}_{locale}` (with `code` for direct lookups). Cache populated on first fetch (`getDatatypeMasterProcessor`). Invalidation on update.

## DB

Single cluster: `code_master`, `code_master_details`, plus per-master tables (`bank_list`, `branch_list`, `apy_configuration`, etc.). Flyway-managed.

## Inbound

Every platform service. Heaviest: accounting (validators), LOS (eligibility config), payments (mode codes).

## Known gotchas

1. **Cache consistency on update** — `createOrUpdateConfiguration` must invalidate the right key. Stale cache = wrong validation everywhere.
2. **`(dataType, dataSubType)` casing matters** — the validators string-match.
3. **No async fan-out** — services have no way to know master data changed. They rely on TTL or explicit eviction.
