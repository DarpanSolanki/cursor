# KG contract layers (2026-06-22)

Standing automation after the "complete KG enrichment" mandate.

## Layers indexed in `kg.db`

| Layer | Builder | What it captures |
|-------|---------|------------------|
| Spine | `build_orchestration.py` | `<Request>` → processors → tables |
| HTTP (XML) | `build_contracts.py` | orchestration `<API>` internal calls |
| HTTP (Java) | `_contract_scan.scan_java_internal_calls` | `callInternalAPI` in batch/writers/consumers (default: all `src/main/java` when `KG_JAVA_SCAN_ALL=1`) |
| DB callbacks | `build_db_contracts.py` | `task_type_api_execution` Flyway COPY + INSERT |
| Batch pipelines | `build_batch_loaders.py` | `*JobLoader.java` registration order → `next` edges |
| Curated | `curated/flows.jsonl`, `diagnostics.jsonl` | Verified money-path order + RCA (e.g. SDCP-9428) |
| Activation | `build_activation.py` | api_master, loader wiring |
| Flow-test export | `contract_graph.py scan` | `flow-test/contracts.jsonl` (671 contracts as of 2026-06-22) |

## One command to refresh everything

```bash
scripts/bin/sync-intelligence.sh --force
```

Runs: platform_scan → contract_graph → chains → footprints → FTG → `kg-switch --force`.

## Query examples

```bash
python3 cursor-bundle/kg/bin/kg.py why deathForeclosureInsuranceJob
python3 cursor-bundle/kg/bin/kg.py orient updateTaskWorkflow
python3 cursor-bundle/kg/bin/kg.py fresh
```

## Honest limits

KG is **structure + contracts + curated failure modes**, not a behavioural spec. Processor business logic and per-tenant DB seed state still require orchestration XML, Java, and `scripts/db-local.sh`.

Canonical human index: `cursor-bundle/brain/platform/cross-service-java-contracts.md`.
