---
name: minimal-fix
description: >-
  Mandatory before proposing or shipping bug fixes: one root-cause layer, no stacked
  guards, ops patch for poison rows. Triggers on fix, RCA ship, duplicate rows, replay.
triggers:
  - minimal fix
  - overkill
  - dedupe guard
  - stacked fix
  - SDCP fix
requires:
  - super-agent
reads:
  - cursor-bundle/memory/feedback_minimal_fix_impact_gate.md
  - .cursor/rules/10-quality-gates.mdc
writes: []
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `minimal fix`, `overkill`, `dedupe guard`, `stacked fix`, `SDCP fix`
- **requires:** `super-agent`
- **reads:** `cursor-bundle/memory/feedback_minimal_fix_impact_gate.md`, `.cursor/rules/10-quality-gates.mdc`
- **writes:** []

# Minimal fix (mandatory gate)

**Default:** smallest change that stops **new** bad state. **Do not** stack write guard + read dedupe + refactor in one PR without proving each layer.

**Also applies to prod/ops SQL** — not Java-only. For CRR/money adhoc UPDATEs: first proposal = smallest contract-native UPDATEs (`FAIL` + `eligible_for_retry=false` + optional `~`); load `.cursor/skills/prod-ops-sql-impact/SKILL.md`. Do not default to local soft-archive ceremony.

Rule: `.cursor/rules/10-quality-gates.mdc` · Memory: `cursor-bundle/memory/feedback_minimal_fix_impact_gate.md` · Ops CRR: `feedback_prod_ops_sql_crr_impact_gate.md`

## Decision ladder (strict order)

| Step | Question | Action |
|------|----------|--------|
| 1 | What **creates** bad state? (write path, reader SQL, missing filter) | Fix **that** first |
| 2 | Is replay/QA-only amplifying a design gap? | One **narrow** guard on the **hot write path** only — or ops idempotency, not every caller |
| 3 | Do dirty rows already exist? | **Post-deploy SQL / IA** — not read-path dedupe for forward traffic |
| 4 | Does user say minimal / no overkill? | **Stop** after step 1–2; drop defensive read layers |

## Write guard vs read resolve

| Prefer | Avoid (unless proven necessary) |
|--------|----------------------------------|
| Fix JOIN/WHERE that double-selects rows | `findDistinct*` on every reader |
| One insert guard on the **actual** batch write method | Same guard on `save` + `saveOne` + booking loop |
| `id != null` → always update (EOD) | Dedupe that blocks updates |
| Post-deploy cleanup for poison rows | Booking read dedupe “just in case” |

## Mandatory output (proposal, JIRA impact, release mail)

```text
Minimal fix: <one line>
Read-path change needed: Yes (why) | No — existing data via patch/replay
Existing prod rows: <list or none>
Regression checked: <paths>
Layers dropped (overkill avoided): <list>
```

## Calibrated precedent — SDCP-10590 (interest accrual duplicates)

**Symptom:** Duplicate `interest_accrual_details` rows on QA2 (same loan, same period); some double-posted.

**Root causes (two, different layers):**

1. **Reader bug** — `loan_product_asset_criteria` join without `is_deleted = false` → same loan processed twice in **one** batch run. **Fix: reader SQL only.**
2. **QA replay** — calc job re-run same day inserts same period again. **Fix: narrow guard on batch `save(List)` only** (`id == null` skip if period exists; `id != null` always save).

**Shipped (minimal — `mfi_integration_v3.4.2.1`):**

- `InterestAccrualCalculationItemReader` + `InterestAccrualBookingItemReader` — `lpac.is_deleted = false`
- `InterestAccrualDetailsDaoService.save(List)` — replay insert guard + `f4ed045` update rule

**Explicitly NOT shipped (overkill):**

- Dedupe on `saveInterestAccrualDetailsEntity` (booking/API only update rows with `id`; DEFAULT API calc is cold / separate ticket if needed)
- `findDistinctPeriodRowsByAccountId` on booking (poison-row read guard — use **cleanup SQL** instead)
- DB unique index (L2 — separate release)

**Ops:** Post-deploy duplicate-row cleanup on QA2 (30 accounts); JIRA `customfield_11336` Post deployment.

## Agent checklist before edit

- [ ] Grep all save/create call sites — fix the path that **inserts** duplicates, not every path that **reads**
- [ ] User asked minimal → challenge any second layer; document **Layers dropped**
- [ ] Impact says what fix does **not** do (existing rows, posting on dirty data until cleanup)
- [ ] Pair with `reuse-queries-java-filter` only when adding SQL — prefer reader one-line fix first

## Related

- JIRA handoff: `.cursor/skills/jira-fix-update/SKILL.md` (Impact must include “not changed” + post-deploy SQL)
- Tiered options: `.cursor/rules/architect-thinking.mdc` + `.cursor/skills/architect-thinking/` (L0 = minimal ship; L1 = index/idempotency)
