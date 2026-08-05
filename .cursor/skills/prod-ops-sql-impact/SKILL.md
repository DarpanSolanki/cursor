---
name: prod-ops-sql-impact
description: >-
  Impact-analyze production/ops mutation SQL (CRR, loan_account, money patches)
  before drafting UPDATE scripts. Prefer contract-native FAIL/SUCCESS/UNKNOWN;
  soft-archive ~ only when LAN finders need detach; never invent status.
  Triggers: prod SQL, adhoc UPDATE, CRR archive, DTFC reset, ops patch script.
triggers:
  - prod sql
  - ops sql
  - adhoc update
  - soft-archive CRR
  - client_request_response_log
  - prod patch
  - DTFC reset
requires: []
reads:
  - .cursor/rules/prod-ops-sql-impact-gate.mdc
  - cursor-bundle/memory/feedback_prod_ops_sql_crr_impact_gate.md
  - scripts/sql/reset/local_reset_disburse_loan_replay_mfi_yugabyte.sql
writes:
  - scripts/sql/adhoc/**
feeds:
  - open-final-file
scripts:
  - scripts/bin/open-final.sh
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `prod sql`, `ops sql`, `adhoc update`, `soft-archive CRR`, `client_request_response_log`, `prod patch`, `DTFC reset`
- **requires:** []
- **reads:** `.cursor/rules/prod-ops-sql-impact-gate.mdc`, `cursor-bundle/memory/feedback_prod_ops_sql_crr_impact_gate.md`, `scripts/sql/reset/local_reset_disburse_loan_replay_mfi_yugabyte.sql`
- **writes:** `scripts/sql/adhoc/**`
- **feeds:** `open-final-file`
- **scripts:** `scripts/bin/open-final.sh`

# Prod / ops SQL impact (skill)

## When to load

User asks for a **production / QA / ops** script that mutates accounting (or other money) tables — especially `client_request_response_log` status / LAN, disbursement_status, CLMT queue JSON.

## Decision ladder (strict — before any SQL)

| Step | Ask | Default action |
|------|-----|----------------|
| 1 | Leave `status` as current contract value (`FAIL`/`SUCCESS`/`UNKNOWN`)? | **Yes** — adjust `eligible_for_retry` / other filtered columns |
| 2 | Must LAN-scoped finders miss the row? | Soft-archive `loan_account_number = '~'||id` only; **keep** contract status |
| 3 | Invent a new status / copy `LOCAL_RESET_ARCHIVED`? | **No** unless Java already recognizes it **and** steps 1–2 proven insufficient |

**Before writing SQL**, state the **minimal permanent** one-liner (smallest UPDATE set that satisfies SUCCESS-skip + retry + re-fire).

## Steps (fail closed)

1. Read `.cursor/rules/prod-ops-sql-impact-gate.mdc` + `feedback_prod_ops_sql_crr_impact_gate.md`.
2. On the **Reported-version train** (fetch upstream tip): grep Repository/DAO + writers for every SET column.
3. Output **impact matrix** + **self-check block** before editing SQL (or same turn if user already asked to fix).
4. Prefer contract-native (example — NEFT v2 FAIL → DTFC reinit):

```sql
-- keep status = 'FAIL' (code contract)
uri = concat_ws(' | ', …, 'ORIG_LAN=' || c.loan_account_number),
loan_account_number = '~' || c.id::text,   -- only if LAN detach needed
eligible_for_retry = false
-- then set loan_account.disbursement_status = 'DTFC_SUCCESS' for re-fire
```

5. Put ops forensics in **`uri`**, not invented `status` values. Copy local-reset `LOCAL_RESET_ARCHIVED` **only after proving** FAIL + retry + optional `~` is not enough.
6. Script ends with `ROLLBACK;` — document human `COMMIT` gate.
7. After edit: print the plain path in the reply (user opens manually). Optional: `bash scripts/bin/open-final.sh <path>` (prints path only). Do **not** `--open` / `open_resource` unless user asked to open in IDE.

## Mandatory self-check (every proposal)

```text
Minimal permanent: <one line>
Contract-native values: Yes (FAIL/…) | No (why)
Anything lost: No | Yes (<what>)
Code-proven: <repo paths that prove SUCCESS-skip / retry>
```

## CRR quick reference (accounting)

| Consumer | Filter | Contract-native FAIL + retry=false (+ optional `~`) |
|----------|--------|-----------------------------------------------------|
| SUCCESS skip / stage-2 skip | `status = 'SUCCESS'` + LAN | Safe — no SUCCESS; `~` detaches LAN finders |
| Retry job | `status = 'FAIL' AND eligible_for_retry` | Safe via `eligible_for_retry=false` (status stays FAIL) |
| ExternalReferenceNoUtil | LAN lookup; bump only if `FAIL` | With `~`: no lastTxn on real LAN; **unsafe** if non-FAIL status + real LAN kept |
| Callbacks | `client_reference_number` (no LAN) | Still finds row; loan by archived LAN may miss — residual |

## Do not

- Invent `PROD_*_ARCHIVED` status strings
- Default to local soft-archive ceremony without answering “is contract-native FAIL enough?”
- Run the script against prod from the agent
- Skip the matrix because "it's just ops SQL"
