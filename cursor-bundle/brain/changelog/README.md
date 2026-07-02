# `cursor-bundle/brain/changelog/` — audit log + flow precedents

Single file: [`CHANGELOG.md`](CHANGELOG.md). Newest first.

## Two layers (do not mix)

| Layer | What | KG? |
|-------|------|-----|
| **Audit log** | Every shipped commit — timeline for humans | **No** |
| **Flow precedents** | Behaviour/flow fixes agents need at `kg cases <apiName>` | **Yes** — opt-in only |

Indexing every audit row into KG bloats the graph and renumbers noise. The graph **spine** comes from code (orchestration, processors, tables). **Precedents** are a thin overlay for “we fixed this flow before.”

## Format (one entry)

```markdown
## YYYY-MM-DD | acct `sha` | service | branch | kg-flow | short title
fetchLoanForeclosureSimulationDetails … apiName … table … error code …
```

**Audit-only** (demo scripts, enrichment meta, gaps, registry):

```markdown
## YYYY-MM-DD | … | kb-only | title
One line — never indexed into KG.
```

Or omit `kg-flow` / use `| kb-only |` in the header.

## Indexing rules (`build_cases.py`)

Indexed into KG **only if**:

- Header contains `| kg-flow |`, or
- Detail starts with `KG-FLOW:`

**Never** indexed if header contains `| kb-only |` or `| skip-kg |`.

Case node id = stable `case:<sha>` (not positional `case:000`).

## Helper

```bash
# Flow fix — refreshes precedents when graph watermark in sync
cursor-bundle/kg/bin/changelog-add.sh --kg-flow \
  "## 2026-06-13 | acct \`sha\` | accounting-v2 | branch | kg-flow | title" \
  "fetchLoanForeclosureSimulationDetails … loan_due_details …"

# Audit only — no KG
cursor-bundle/kg/bin/changelog-add.sh \
  "## 2026-06-13 | workspace | kb-only | demo script tweak" \
  "scripts/dpic only — no flow change."
```

## Hard rule

Every **service code** commit gets a CHANGELOG row. Only **flow-changing** fixes get `kg-flow`.
