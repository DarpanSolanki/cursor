---
name: feedback_minimal_fix_impact_gate
description: "Before shipping any fix: prefer minimal write-path guard; justify read-path/defensive code; existing prod rows; races; no new issues. Mandatory gate."
metadata:
  node_type: memory
  type: feedback
---

## Standing rule (user-approved)

When proposing or implementing a bug fix, **do not stack fixes** (write guard + read resolve + broad refactor) without proving each layer is needed. **Start minimal.** Run this gate **before** code and **state the outcome in impact analysis / release details**.

## Mandatory gate (all five — answer in chat or release impact)

1. **Root cause layer** — Is the bug bad **data created** (write path), bad **lookup** (read path), or **both**? Fix the layer that **causes** new bad state first (usually write/create).

2. **Minimal fix** — What is the **smallest** change that stops new incidents? Example (SDCP-10255): block a **second** foreclosure request when one is already **PENDING** on the same loan — do not add “pick latest row” on approve unless still required.

3. **Is defensive read redundant?** — If write-path guard is correct, **read-path resolve is often not needed for forward traffic**. Say explicitly: “Resolve not required if create guard + …”

4. **Existing production rows** — Guard does **not** heal rows already in DB. List: need **data patch / IA**, **replay**, or **one narrow read fallback** only for approve/sync on dirty data. Call out in impact: “Loans stuck before deploy need manual fix.”

5. **New issues from our change** — Race (two parallel creates), retry/replay, regression happy path, cross-service caller (Payments sync, batch expiry). Grep all call sites; one regression scenario in dev testing.

## Write guard vs read resolve (pattern)

| Situation | Prefer |
|-----------|--------|
| Duplicate rows because create allowed second PENDING | **Block on create** (or fail with clear error / reuse existing per product) |
| Approve fails today on 2 rows | **Data patch** for known LANs + create guard going forward |
| Approve must work without ops patch on unknown duplicates | **Then** add narrow read: latest PENDING by created_on on approve path only |
| User asked for minimal fix | **Do not** add read resolve “just in case” if create guard + prod patch plan is enough |

## Agent must challenge own first suggestion

If the first idea was “guard + resolve”, **re-evaluate**: explain why resolve is or is not needed. User expectation: **minimal, clean impact analysis — no new issues from over-fixing.**

## Tie-in

- Implementation: `.cursor/rules/minimal-fix-impact-gate.mdc`
- Release impact bullet: `feedback_release_details_final.md` (Existing prod / Not affected / What fix does **not** do)
- Broader call sites: `no-flow-break-impact-check.mdc`

## Calibrated example — SDCP-10255

- **RCA:** Two active PENDING foreclosure requests for same loan → approve lookup expected one row → sync failed, loan stuck frozen.
- **Minimal fix:** Reject or skip **creating** a second PENDING request for the same loan.
- **Resolve on read:** Not required for **new** loans after guard. Still need **IA/data patch** for LAN 6000048598 (and any other pre-existing duplicates).
- **Do not** broadly change every `findOne` to `findLatest` without justification.

## Calibrated example — SDCP-10590 (interest accrual)

- **RCA:** (1) LPAC join without `is_deleted` → double loan pick in one batch run. (2) QA replay of calc batch → second insert same period.
- **Minimal fix:** Reader `lpac.is_deleted = false` on calc + posting readers; **batch-only** `save(List)` insert guard (`id != null` always saves for EOD update).
- **Resolve on read:** **Not shipped** — booking `findDistinct*` rejected as overkill; existing QA2 dupes → post-deploy cleanup SQL.
- **Do not** add dedupe on `saveInterestAccrualDetailsEntity`, booking loops, and `save(List)` in the same PR without justification.
- **Skill:** `.cursor/skills/minimal-fix/SKILL.md`
