# KG layers — what the graph knows vs what it does not

The KG is **not** runtime truth. It is a **verified index** built from orchestration XML, Java static analysis, brain docs, and hand-curated overlays. Use `kg orient <request>` then read orchestration + DB.

## Layer map

| Layer | Builder | Edge types | What it answers |
|-------|---------|------------|-----------------|
| **Spine** | `build_orchestration.py` | `invokes` (seq, **cond**=function_code), `calls_api` | Ordered processor chain per Request |
| **Internal dispatch** | `build_internal_calls.py` | `calls` (request↔request, processor→request) | Java `put("api_name", …)` nested Request flows |
| **CRUD** | `build_dataaccess.py` | `reads`, `writes`, `deletes` | Which tables each processor touches |
| **Services** | `build_services.py` | `calls`, `emits`, `resolves_to` | Cross-service dependencies |
| **Activation** | `build_activation.py` | `activates`, `ui_calls`, `wires` | api_master seeds, webapp routes, platform-lib anchors |
| **Semantics bone** | `build_semantics_bone.py` | `maps_to`, `sets_txn_type`, `has_batch_cfg`, `explains`, `constrains`, `listens_on` | **What is X**: `entity`, `txn_type`, `gl_mech`, `batch_cfg`, `redis_key`, `framework`, `server` — query via `kg concept` / search |
| **Pipeline** | `kg/curated/flows.jsonl` | `next` | Curated job order (EOD/DPIC) — **not** orchestration order |
| **Behavioral** | `build_failuremodes.py` + `curated/diagnostics.jsonl` | `has_failure_mode`, `checks` | Silent failure surfaces + verified root causes |
| **Precedents** | `build_cases.py` | `touches`, `hit_error` | Shipped fixes (`\| kg-flow \|` only) |
| **Docs** | `build_docs.py` | `mentions`, `documents` | Brain doc ↔ flow links |

## Confirmed properties (run `kg audit`)

### `invokes.cond`

Every `invokes` edge carries `cond`:

- `*` — no `function_code` gate (default path)
- `DEFAULT`, `APPROVE`, `INITIATE`, … — from enclosing `<Control pattern="${function_code}" value="…">`

**`note` on invokes is always empty** — branching is in `cond` only.

### `next` edges

Only **curated** pipeline order (currently DPIC 3-step + interest EOD + runEOD→reports). These are **separate batch jobs**, not sequential processors inside one Request.

Extend: `cursor-bundle/kg/curated/flows.jsonl` → `build.sh`.

### Behavioral layer

Two tiers:

1. **Curated `diag` nodes** (~10) — verified failure modes with symptom, mechanism, live SQL, runbook. Source: `kg/curated/diagnostics.jsonl`.
2. **Auto `diag:auto.*`** (~474) — regex scan for `return null`, `BigDecimal.ZERO`, empty collections, swallowed catches. **Candidates only** — use `kg why <request>` to list, then verify in code.

`has_failure_mode` links processors/requests to both tiers. Prefer curated diags for RCA; auto surfaces are a grep substitute.

**`kg why <request>` reachability (generic):** walks orch `invokes` **plus** nested `calls` (internal dispatch), `calls_api`→request resolution, processor `implements`→symbol failure modes, and one-hop curated `related` diags — so top-level Requests that only dispatch child flows still surface nested RCAs without per-flow curated patches.

### Processor DB footprint

~33% of in-flow processors have **no** `reads/writes/deletes` edge. This is **mostly expected**:

- Validators, pure compute, inter-service API callers
- build_dataaccess logs ~466 “no-db-helper” call sites vs ~11 genuine unresolved DAO paths

Use `kg crud <request>` for money-path write-sets.

### Thin repos (activation gap)

`trustt-platform-initial-setup`, `trustt-platform-lib`, `trustt-platform-webapp` have **no orchestration XML** in the same shape as accounting. Before `build_activation.py` they appeared as a single `service:*` node each.

`build_activation.py` now indexes:

- Flyway `api_master` INSERTs → `activation:api_master:*` → `activates` → `request:*`
- Webapp `getApiUrl('…')` constants → `ui_calls`
- platform-lib framework class anchors → `wires`

Deep activation semantics: `cursor-bundle/brain/platform/system-activation-and-wiring.md`.

## Commands

```bash
python3 cursor-bundle/kg/bin/kg.py audit      # this layer report
python3 cursor-bundle/kg/bin/kg.py why disburseLoan
python3 cursor-bundle/kg/bin/kg.py crud disburseLoan
python3 cursor-bundle/kg/bin/kg.py stale
cursor-bundle/kg/bin/build.sh --force
```

## Extending without sprawl

| Add | Where |
|-----|--------|
| New verified bug class | `kg/curated/diagnostics.jsonl` |
| New pipeline order | `kg/curated/flows.jsonl` |
| Shipped flow fix precedent | `changelog-add.sh --kg-flow` |
| Stable operational fact | One brain doc under `cursor-bundle/brain/` |
| Workspace audit only | `.cursor/changelog.md` (not indexed) |
