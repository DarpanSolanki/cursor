<!-- VERBATIM archive of former alwaysApply `.cursor/rules/principal-architect-knowledge-base.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Principal architect context (sliProd)

## Before deep work

1. **Identify the service** (`trustt-platform-accounting`, `trustt-platform-los`, …) and run **git** in that repo root, not assumed workspace root.
2. **Skim** `.cursor/architecture.md` and the relevant section of `.cursor/accounting-flows.md` or `system_brain/flows/*` for money flows.
3. **Check platform-lib** (`.cursor/platform-lib.md`) before reimplementing orchestration, HTTP entry, cache, or Kafka plumbing.

## Behaviour

- **Contracts**: additive-only API/Kafka/ExecutionContext changes; grep callers across LOS, payments, batch, webapp, reporting (see `api-contract-safety.mdc`).
- **Accounting / money**: trace orchestration XML → processors → `postTransaction` / ledger tables; run through `accounting-financial-flow-preflight.mdc` and signoff gate when figures or GL are touched.
- **Risks**: read `.cursor/gaps-and-risks-digest.md` for open High rows (escalate to full `.cursor/gaps-and-risks.md` when GAP-id/area flagged or digest missing/stale); do not dismiss Redis, bank replay, or sync field requirements.
- **Documentation**: prefer updating `system_brain/` for verified operational facts and `.cursor/skills/accounting-knowledge/` topic files when accounting-v2 behaviour changes (see thin `accounting.mdc` knowledge-sync routing).

## Knowledge base files (this workspace)

| File | Purpose |
|------|---------|
| `.cursor/architecture.md` | Services, comms, data flow |
| `.cursor/platform-lib.md` | Shared libs and extension points |
| `.cursor/accounting-flows.md` | Accounting entry points and major flows |
| `.cursor/service-contracts.md` | HTTP/Kafka/context contracts |
| `.cursor/gaps-and-risks-digest.md` | Session High gaps (SoT: `gaps-and-risks.md`) |
| `.cursor/conventions.md` | Naming, DB, orchestration habits |

These complement — do not replace — `AGENTS.md`, `.cursor/rules/*.mdc`, and `AGENTS.md`.
