---
name: reference_system_kg
description: "The one core knowledge graph (SQLite) at cursor-bundle/kg/ — how to query, extend, and keep it current for issue analysis & feature scoping."
metadata: 
  node_type: memory
  type: reference
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

**The single core knowledge artifact** is our own in-tree graph at `/home/darpan/Documents/sliProd/cursor-bundle/kg/` — a **SQLite store** (`data/kg.db`, stdlib `sqlite3`, no install, in-folder), built from the canonical `data/kg.jsonl`. No dependency on the external `mcp__kms-kb__*` (down/optional). Built 2026-06-10. **Architecture rule: new knowledge plugs into this graph (a `doc` node auto-links, or a curated edge) — do NOT create loose markdown islands; the workspace must not sprawl into thousands of orphan files.** Keeping it current is mandatory — see [[feedback_keep_knowledge_current]].

**Query** (provenance-tagged, file:line; FTS5 search; recursive-CTE impact/path):
```
cursor-bundle/kg/bin/kg flow <request>      # Request->Processor chain (flow spine) + "documented in" + DB footprint summary
cursor-bundle/kg/bin/kg crud <request>      # full DB footprint of a flow: per-processor reads/writes/deletes + READ-SET/WRITE-SET (the flow-simulation map)
cursor-bundle/kg/bin/kg writes|reads|deletes <table>   # reverse: which processors/flows write|read|delete a table (CRUD blast-radius)
cursor-bundle/kg/bin/kg deps <service>      # what a service calls / is called by
cursor-bundle/kg/bin/kg cases [<flow>]      # PRECEDENT — shipped fixes; "fixed this before?"
cursor-bundle/kg/bin/kg error <code>        # cases that hit an error code (who, fix SHA)
cursor-bundle/kg/bin/kg table <name>        # owning repo + entity + cases that touched it
cursor-bundle/kg/bin/kg docs <id> | impact <id> | path <a> <b> | search "<text>" | node <id> | stats
cursor-bundle/kg/bin/kg fresh               # one-line verdict: is KG branch-correct for the LIVE checkout? (SessionStart hook shows it)
cursor-bundle/kg/bin/kg doctor              # health + freshness + branch-watermark drift
cursor-bundle/kg/bin/kg watermark           # per-repo branch@sha the knowledge reflects vs live HEAD; flags WIP/feature-branch & drift
cursor-bundle/kg/bin/kg stale [<doc>]       # docs citing repo files that no longer exist (drift vs code)
cursor-bundle/kg/bin/kg sql "SELECT ..."    # power-user read-only SQL
```
**Rebuild after a sync / new knowledge** (deterministic): `cursor-bundle/kg/bin/build.sh` (feeders: build_orchestration / build_services / build_tables / **build_dataaccess** / build_docs / build_cases / build_db). The build **stamps a per-repo `branch@sha` watermark** into `data/stats.json` so `kg doctor`/`kg watermark` know exactly which branch the knowledge is current to — and flag knowledge built off a **feature/WIP branch** as provisional. **For a feature/customer branch it also resolves the UPSTREAM release branch it was forked from** (most-recent common ancestor + commit delta) so you anchor the KG to that stable base and treat only `base..HEAD` as in-development (upstream = source of truth). **Auto-update is judgment-gated:** fold a found change into the docs only if it's correct AND stable (release-train, reachable, not flagged/dirty) — the WIP-vs-stable gate in [[feedback_keep_knowledge_current]]; never blind-rewrite curated docs.

**Coverage (~6,400 nodes / ~23,260 edges):** Request→Processor flow for **all 14 orchestrated repos** (accounting, actor, los, payments, task, batch, masterdata, authorization, notifications, approval, audit, api-gateway, dms, reporting — orchestration XML auto-detected by content, any filename); **every loan transaction** has its chain + a curated authoritative `documents` doc; platform **data model** (774 `@Table` nodes + `owns` edges); **DB-access (CRUD) layer — `processor -[reads|writes|deletes]-> table` edges (~7,840; 2,335/3,476 = 67% of processors carry one)** resolved statically through Processor→DAOService/Repository→@Entity, following custom-base repos, interface→impl, `this.`/bare intra-class delegation, and wrapped calls; fine op in `note` (read/upsert/soft_delete/native_select/native_update/native_delete…); soft-deletes (`is_deleted=true` UPDATE) correctly land as **writes**, not deletes; 17 services + cross-service deps; all `claude/**/*.md` folded in as `doc` nodes auto-linked (`mentions`); **89 `case` nodes** mined from CHANGELOG (the self-learning layer, linked `touches`→requests/tables, `hit_error`→codes). DB-access is **near-complete: only ~11 genuine missed DB call-sites platform-wide** (`build_dataaccess` reports `real-misses` vs `no-db-helpers` — the ~33% of processors without an edge are pure compute/validation that correctly touch no table; `missing_table_refs=0` ⇒ zero fabricated edges). The honest metric is **real-misses**, not raw "unresolved" (which counts no-DB helper calls like `getFullName`/`formatDate`). **Self-learning loop:** ship fix → CHANGELOG entry naming Request/table/error → `build.sh` → queryable `case`. The `changelog-add` skill does the rebuild. Per [[feedback_keep_knowledge_current]].

**Branch-safety (one KG, many branches) — pinpoint, automatic:** the KG is a single snapshot of the live checkout. (1) **Auto drift-guard + AUTO-REBUILD**: every knowledge query checks the live checkout vs the build; on drift (branch switched / commits advanced / **uncommitted edits**) it **rebuilds for the current checkout before answering** — cache-restore ~1s if that branch-set was built before, else a one-time full build — so analysis is always branch-correct. `--no-drift-check` skips the check; `KG_NO_AUTO_REBUILD=1` = warn-only (scripts/CI). (2) **Composite cache** (`data/cache/`): keyed on every repo's `branch+HEAD+dirty-diff` + the `cursor-bundle/` doc corpus (correct even when dirty / docs edited); LRU keep 8. (3) **SessionStart hook** runs `kg fresh`. Rule: to analyse on branch X, just check out X — the next `kg` query auto-rebuilds. Editing `build.sh` watermark logic ⇒ `build.sh --force` once. Full scenario matrix: `cursor-bundle/kg/BRANCH-SAFETY.md`.

Use via the **`system-kg`** skill. DPIC flow spine: `claude/dpic/04-dpic-flow.md` (branch `feature/delayed_payment_interest`). Deep accounting semantics in `claude/accounting/08-gl-posting-engine.md`, `claude/engines/posting-engine.md`, worked example `claude/accounting/worked-examples/death-foreclosure-walkthrough.md`. See [[reference_workspace_canonical_setup]].
