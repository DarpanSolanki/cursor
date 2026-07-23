# Rules — always-on coding & safety guidance

Production-incident-derived rules. **Read the relevant ones before any change to that surface.** They were `.mdc` (Cursor) until 2026-05-07; renamed to `.md` so Claude can discover them.

## Cross-cutting (apply to every change)

- [`no-flow-break-impact-check.md`](no-flow-break-impact-check.md) — non-negotiable impact analysis (call-sites, EC safety, flow invariants, state regression, cross-module callers, response contract).
- [`multi-path-state-persistence-safety.md`](multi-path-state-persistence-safety.md) — when multiple paths can write the same state, ensure idempotency + monotonic-forward transitions. Pairs with `feedback_no_inmem_mutation_after_cas` memory.
- [`execution-context-discipline.md`](execution-context-discipline.md) — EC keys must be read/written safely; no leak across processors; no overwrite of a downstream-needed key.
- [`api-contract-safety.md`](api-contract-safety.md) — never change an existing response semantic; add new fields, keep old behaviour. Born of the `charges_configured` LOS-KFS incident.
- [`tiered-solution-approach.md`](tiered-solution-approach.md) — after analysis emit full OPTIONS BOARD L0+L1+L2+L3 (`N/A` one-liner OK); include code options; evidence-only next-step forbidden.
- [`discuss-before-updating.md`](discuss-before-updating.md) — confirm scope with the user before structural changes.
- [`novopay-framework-awareness.md`](novopay-framework-awareness.md) — SOF / orchestration / processor / `<Transaction>` block awareness; no `@Transactional` on processors.

## Surface-specific

- [`gateway.md`](gateway.md) — API gateway / authorization filter / forward routing.
- [`los.md`](los.md) — LOS-side patterns (sync orchestration, function_sub_code branching).
- [`payments.md`](payments.md) — payments service / collection consumer.
- [`batch.md`](batch.md) — batch jobs (chunk size, dedup, idempotency on retry).
- [`events.md`](events.md) — Kafka producer / consumer patterns; correlation IDs.
- [`platform-lib.md`](platform-lib.md) — platform-lib changes have cross-service blast radius; verify every consumer.
- [`repository-layer-no-comments.md`](repository-layer-no-comments.md) — Spring Data repos stay minimal; no narrative comments.

## When to invoke

Pull the relevant rule into the head of any analysis or fix turn. Rules are short (50-200 lines each) and incident-derived — they have negative-case examples that prevent the next regression.

## Cross-links

- Convention summary (style, formatting, comment policy): [`conventions.md`](conventions.md).
- Concurrency guidance for multi-writer rows: `~/.claude/projects/-home-darpan-darpan/memory/feedback_concurrency_contract_audit.md`.
- "No in-memory mutation after CAS": `~/.claude/projects/-home-darpan-darpan/memory/feedback_no_inmem_mutation_after_cas.md`.
