# Feedback: prod ops / CRR — contract-native values first (FAIL over invented archive)

**Date:** 2026-07-19 (revised)  
**Incident:** NEFT v2 FAIL → DTFC_SUCCESS reinit (`scripts/sql/adhoc/prod_neft_v2_fail_reset_to_dtfc_reinit.sql`). Rejected defaults: `PROD_NEFT_V2_FAIL_ARCHIVED`, copying `LOCAL_RESET_ARCHIVED` as the first proposal.

## Why the earlier miss (standing)

Agents defaulted to **local soft-archive ceremony** (`~` LAN + `LOCAL_RESET_ARCHIVED`) because that is what local replay scripts do, and ship gates (ship-discipline / money ship-loop) **do not cover adhoc SQL**. There was no **contract-native first** ladder: nobody asked “does leaving `status=FAIL` already satisfy SUCCESS-skip + retry safety?” before inventing archive statuses or copying local-reset wholesale.

## Standing rule

Prefer **minimal but permanent** patterns that are **correct**, **will work**, **nothing lost**, and **100% proven in Java**:

1. Start from the **runtime contract** — what code actually equals/filters (`SUCCESS` / `FAIL` / `UNKNOWN`, `eligible_for_retry`, LAN finders) — not local-reset habits or invented statuses.
2. First proposal = the **smallest set of UPDATEs** that satisfy SUCCESS-skip + retry off + re-fire entry.
3. Soft-archive (`loan_account_number = '~'||id`) **only when** LAN-scoped lookups must detach the row from the real LAN.
4. Soft-archive status markers (`LOCAL_RESET_ARCHIVED`, `LOCAL_FORCE_STAGE_ARCHIVED`) are **local-forensic** — copy only after proving contract-native `FAIL` (+ retry flag / optional `~`) is insufficient.
5. **Never invent** `PROD_*_ARCHIVED` (or any status Java does not already recognize).

### Calibrated minimal (this incident)

| Goal | Minimal permanent |
|------|-------------------|
| SUCCESS skip / LAN finders miss row | optional `~`||id |
| Retry job does not re-pick | keep `status='FAIL'`, set `eligible_for_retry=false` |
| Re-fire entry | set `loan_account.disbursement_status='DTFC_SUCCESS'` (or CLMT path) |
| Forensics | ORIG_LAN / notes in `uri` — **not** a new status |

## Decision ladder (strict)

| Step | Ask | Action |
|------|-----|--------|
| 1 | Can we leave `status` as the current contract value (`FAIL` / `SUCCESS` / `UNKNOWN`)? | Prefer yes — pair with `eligible_for_retry` / other columns the code already filters |
| 2 | Do LAN-scoped finders still see a dangerous row? | Only then soft-archive LAN with `~`\|\|id; keep contract status |
| 3 | Still need a non-contract status? | **Stop** — do not invent; prove Java already recognizes the literal |

Challenge over-engineered neutralize/archive when **FAIL (or existing enum) already satisfies** SUCCESS-skip / money-path safety.

## Mandatory self-check (every prod SQL proposal)

```text
Minimal permanent: <one line>
Contract-native values: Yes (FAIL/…) | No (why)
Anything lost: No | Yes (<what>)
Code-proven: <repo paths that prove SUCCESS-skip / retry>
```

## Setup (workspace)

- Rule: `.cursor/rules/prod-ops-sql-impact-gate.mdc`
- Skill: `.cursor/skills/prod-ops-sql-impact/SKILL.md`
- Minimal-fix scope includes **prod/ops SQL** (not Java-only)
- Autopilot OPS_SQL: run prod-ops skill **and** answer “is contract-native FAIL enough?”

## Pair with

- `feedback_minimal_fix_impact_gate.md` — same minimal-layer discipline for SQL
- `20-ship-gates.mdc` — Ops / prod hotfix front
