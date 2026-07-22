<!-- VERBATIM archive of former alwaysApply `.cursor/rules/self-learning-kg.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Self-learning knowledge system (cursor-bundle)

This workspace **learns from every shipped fix**. The graph is not static reference — it is rebuilt from live code + brain docs + changelog.

## The loop (mandatory after stable fixes)

```
ship fix → prepend cursor-bundle/brain/changelog/CHANGELOG.md → cursor-bundle/kg/bin/build.sh → kg cases <flow>
```

1. **Changelog** — 2 lines per entry (header + detail). Format: `brain/changelog/README.md`. Helper: `cursor-bundle/kg/bin/changelog-add.sh`.
2. **Rebuild** — `cursor-bundle/kg/bin/build.sh` (or `scripts/bin/kg-enrich.sh`). Each changelog entry becomes a **`case`** node linked to requests/tables/error codes.
3. **Doc sync** — if behaviour changed on a **release-train** branch, update the **single** relevant `cursor-bundle/brain/` doc in the same turn. No new orphan markdown files.

## WIP-vs-stable gate (judgment, not blind automation)

**Do NOT** fold provisional code into stable brain docs when ANY hold applies:

- Feature/WIP branch (`feature/*`, `sli_*`, ticket branches) — anchor to upstream release base (see `kg watermark`)
- Behind feature flag, `TODO`/`FIXME`, `@Deprecated`, unreachable from orchestration
- Uncommitted / dirty working tree

For WIP: note in `gaps-and-risks.md` or feature doc; rebuild KG for **code spine** only. Stable docs stay on release-base semantics.

Full gate: `cursor-bundle/memory/feedback_keep_knowledge_current.md`.

## Branch watermark + auto-rebuild

- **Watermark** — `python3 cursor-bundle/kg/bin/kg.py watermark` — per-repo `branch@sha` the KG was built from vs live HEAD.
- **Fresh** — `kg fresh` — one-line verdict (session hook + `.cursor/workspace-kg-state.md`).
- **Doctor** — `kg doctor` — stale sources + watermark drift + CRUD coverage.
- **Auto-rebuild** — any knowledge query (`kg flow`, `why`, `crud`, `cases`, …) **auto-runs `build.sh`** when repo branch/commit/dirty drifts. Cache restore ~1s if that branch-set was built before. Opt out: `KG_NO_AUTO_REBUILD=1`.
- **Doc-only edits** — brain `.md` or CHANGELOG newer than `kg.db` → **warn**; run `build.sh` manually (no auto-rebuild on doc-only drift).

Details: `cursor-bundle/kg/BRANCH-SAFETY.md`, `cursor-bundle/memory/reference_system_kg.md`.

## Agent discipline (brain-first)

Before grepping source on RCA/fix/feature work:

1. `cursor-bundle/memory/MEMORY.md`
2. `cursor-bundle/brain/` (symptom index: `brain/runbooks/00-INDEX.md`)
3. `python3 cursor-bundle/kg/bin/kg.py why <request>` · `flow` · `crud` · `cases` · `error`
4. `scripts/db-local.sh` (local evidence)
5. Service code last

## Session state

Read **`.cursor/workspace-kg-state.md`** (auto-updated on workspace open / session start) for KG freshness + watermark snapshot.

If **`.cursor/.pending-kg-rebuild`** exists after a commit: run `scripts/bin/kg-enrich.sh` when the fix is stable and changelog is prepended.
