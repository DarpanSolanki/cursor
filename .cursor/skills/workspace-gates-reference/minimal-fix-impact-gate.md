<!-- VERBATIM archive of former alwaysApply `.cursor/rules/minimal-fix-impact-gate.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Minimal fix + impact gate

Before **proposing or implementing** any bug fix (especially money/foreclosure/repayment/state), run the gate in `cursor-bundle/memory/feedback_minimal_fix_impact_gate.md`.

**Scope:** Applies to **Java/service fixes and prod/ops mutation SQL** (`scripts/sql/adhoc|deploy|setup`). For CRR/ops SQL, also run `prod-ops-sql-impact` and prefer **contract-native** values (`FAIL`/`SUCCESS`/`UNKNOWN`) over invented archive status — see `feedback_prod_ops_sql_crr_impact_gate.md`.

## Hard rules

1. **Prefer write-path / create-path guard** when the root cause is duplicate or invalid **new** rows. Do not add read-path “pick latest / resolve” unless write guard alone is insufficient. For ops SQL: prefer the **smallest UPDATE set** that satisfies code filters — challenge soft-archive/new status when existing enum already works.

2. **If user prefers minimal** — state clearly whether read-path change is **redundant** (forward traffic) vs **only for existing dirty DB** (ops patch instead).

3. **Existing production data** — create guard does not fix rows already in DB. Impact analysis **must** say: manual patch / replay needed for named LANs, or justify a **narrow** read fallback.

4. **Challenge stacked fixes** — guard + resolve + refactor in one PR needs explicit justification per layer. Default: **one minimal layer** + prod patch plan.

5. **No new issues** — grep call sites; concurrent create/race; retry/replay; happy-path regression. Document in impact / dev testing.

6. **Reuse queries (mandatory)** — Read `.cursor/skills/reuse-queries-java-filter/SKILL.md` before any `*Repository.java` / `*DAOService.java` edit. Ladder: reuse + Java → extend existing (no perf degrade) → new `@Query` last.

8. **Minimal-fix skill** — Read `.cursor/skills/minimal-fix/SKILL.md` when user says minimal, no overkill, or when tempted to add dedupe on multiple layers. Document **Layers dropped**.

7. **Significant perf (along the way)** — In the same fix scope, include **significant** perf wins (batch N+1, hot-path duplicate fetch); skip **slight** gains. See `cursor-bundle/memory/feedback_significant_perf_with_fix.md` and **`.cursor/rules/hot-path-perf-gate.mdc`** (workspace-wide, not batch-only).

## Output (required in proposal or release impact)

```text
Minimal fix: <one line>
Read-path change needed: Yes (why) | No — existing data via patch/replay
Existing prod LANs: <list or none>
Regression checked: <paths>
Significant perf in scope: Yes (<what>) | No — none material in this path
Hot-path scan: PASS | WARN — scripts/bin/hot-path-scan.sh --from-pending
```

Pairs with `no-flow-break-impact-check.md`, `discuss-before-updating.mdc`, and `hot-path-perf-gate.mdc`.
