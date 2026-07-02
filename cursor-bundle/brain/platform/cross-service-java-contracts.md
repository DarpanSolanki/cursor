# Cross-service contracts — Java + DB seed (XML-invisible layer)

**KG layer:** `HTTP_INTERNAL_JAVA` contracts from `cursor-bundle/kg/bin/_contract_scan.py`  
**Query:** `python3 cursor-bundle/kg/bin/kg.py deps <request|service>` after rebuild  
**Diagnostics:** `kg why deathForeclosureInsuranceJob` → `diag:distributed_txn.*`

## Why this exists

The KG spine is built from **orchestration XML** (`<Request>` → `<Processor>` → `<API>`). Many money paths **do not** declare cross-service hops in XML:

| Pattern | Example | Indexed as |
|---------|---------|------------|
| Batch `ItemWriter` / `Tasklet` calls `callInternalAPI` | `DeathForeclosureInsuranceWriter` → `deleteTask`, `postTransaction` | `contract:http-java:…` |
| Same-JVM internal API from service class | `DeathForeclosureBillingSyncService` → `loanAccountBillingJob` | `contract:http-java:…` |
| Task workflow DB callbacks | `task_type_api_execution` → arbitrary `api_name` on APPROVE/REJECT | `diag:distributed_txn.task_workflow_db_callbacks` |
| Kafka consumer → orchestration or direct service | `LmsMessageBrokerConsumer` → `disburseLoan` | `contract:kafka:…` (curated) |
| `ConfigValue` / masterdata on cache miss | LOS EOD → `getConfigurationDetails` PROP-KEY | `diag:config_resolution` + GAP-076 |

**Scan coverage (2026-06-22):** 14 repos, ~1818 orchestration requests, ~390 XML `<API>` edges, **+242 Java internal call sites** → **+183 HTTP_INTERNAL_JAVA contracts** (31 money HTTP total with curated overlays).

## Death foreclosure insurance batch (`deathForeclosureInsuranceJob`)

**SDCP-9428 (shipped):** task↔accounting ordering fix for reverse-feed batch.

| Path | Order (current) | Txn boundary |
|------|-----------------|--------------|
| **RE_UPLOAD** (`Pending for FR`) | Save `death_foreclosure_details` → staging `claim_status=REJECTED` → `updateTaskWorkflow` | Accounting chunk; task HTTP separate txn |
| **APPROVE** | Billing sync → amount engine → `deleteTask` (non-fatal) → `postTransaction` → status/staging APPROVED → closure → LOS sync → parent part-prep | `postTransaction` separate txn; chunk rolls back accounting DB on fatal |

**Residual drift (low):** `deleteTask` is **non-fatal** before `postTransaction` — if GL posting fails, task may already be deleted. Ops: reconcile `mfi_task.task` vs `death_foreclosure_details`.

**Masterdata collateral failure (GAP-076):** EOD LOS config miss overload — not a task/accounting ordering bug.

## Other high-value Java contract clusters

| Producer (job/API) | Callee | Service | Money |
|--------------------|--------|---------|-------|
| `deathForeclosureInsuranceJob` | `updateTaskWorkflow`, `deleteTask`, `postTransaction`, `loanAccountBillingJob` | task, accounting | Yes |
| `pushPendingLMSUpdates` / collections batch | `collectionLoanRepayment`, `updateCollectionBatchDetails` | accounting | Yes |
| `loanAdvanceRepayment` | `loanRepayment` | accounting | Yes |
| `loanPrepayment` / foreclosure | `createTaskWorkflow` | task | Yes |
| ENACH / SI presentation tasklets | `loanRepayment` | accounting | Yes |
| `proactiveExcessAmountRefund` | `postTransaction` | accounting | Yes |
| `expirePendingMandates` | `expireMandateRegistration` | accounting → LOS | Yes |
| Task `updateTaskWorkflow` | DB-driven via `task_type_api_execution` | varies | Often |

## Task DB callback model

```
updateTaskWorkflow (task service)
  → UpdateTaskWorkflowProcessor
  → task_type_api_execution (action=APPROVE|REJECT|UPDATE)
  → TaskWorkflowAPIExecutionService.callAPI(api_name, …)
  → HTTP to accounting / LOS / actor (not in caller's orchestration XML)
```

Seed tables: `mfi_task.task_type_api_execution`, `workflow_master`, `workflow_stage_details`.

## Regenerating

```bash
cd /home/darpan/Documents/sliProd
python3 cursor-bundle/kg/bin/build_contracts.py | wc -l   # contract nodes+edges
bash cursor-bundle/kg/bin/build.sh --force               # full KG rebuild
python3 cursor-bundle/kg/bin/kg.py validate
python3 cursor-bundle/kg/bin/kg.py deps deathForeclosureInsuranceJob
```

Extend curated overlays: `cursor-bundle/kg/curated/diagnostics.jsonl`, `CURATED_HTTP_CONTRACTS` in `_contract_scan.py`.
