<!-- Relocated verbatim from .cursor/rules/architect-thinking.mdc. Edit skill topics; thin architect-thinking.mdc only routes here. -->

# Principal architect context (sliProd)

(sliProd)

## Before deep work

1. **Identify the service** (`trustt-platform-accounting`, `trustt-platform-los`, …) and run **git** in that repo root, not assumed workspace root.
2. **Skim** `.cursor/architecture.md` and the relevant section of `.cursor/accounting-flows.md` or `system_brain/flows/*` for money flows.
3. **Check platform-lib** (`.cursor/platform-lib.md`) before reimplementing orchestration, HTTP entry, cache, or Kafka plumbing.

## Behaviour

- **Contracts**: additive-only API/Kafka/ExecutionContext changes; grep callers across LOS, payments, batch, webapp, reporting (see `api-contract-safety.mdc`).
- **Accounting / money**: trace orchestration XML → processors → `postTransaction` / ledger tables; run through `.cursor/skills/accounting-knowledge/preflight-signoff.md` and signoff gate when figures or GL are touched.
- **Risks**: read `.cursor/gaps-and-risks-digest.md` (escalate to full `.cursor/gaps-and-risks.md` when GAP-id/area flagged) for known edge cases; do not dismiss Redis, bank replay, or sync field requirements.
- **Documentation**: prefer updating `system_brain/` for verified operational facts and `.cursor/skills/accounting-knowledge/` when accounting-v2 behaviour changes.

## Knowledge base files (this workspace)

| File | Purpose |
|------|---------|
| `.cursor/architecture.md` | Services, comms, data flow |
| `.cursor/platform-lib.md` | Shared libs and extension points |
| `.cursor/accounting-flows.md` | Accounting entry points and major flows |
| `.cursor/service-contracts.md` | HTTP/Kafka/context contracts |
| `.cursor/gaps-and-risks-digest.md` | Session High gaps (escalate to full `gaps-and-risks.md` when flagged) |
| `.cursor/conventions.md` | Naming, DB, orchestration habits |

**Also**: `.cursor/docs/*.md` (glossary, patterns, anti-patterns, FAQ, testing) and **`system_brain/flows/*.md`** (indexed in `.cursor/architecture.md` §§11–12).

These complement — do not replace — `.cursorrules`, `.cursor/rules/*.mdc`, and `AGENTS.md`.

---

