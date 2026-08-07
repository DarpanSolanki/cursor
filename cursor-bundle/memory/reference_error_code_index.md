---
name: reference-error-code-index
description: How the KG error-code index is built and what it may not claim — throw sites are branch truth, message templates are runtime only
metadata:
  type: reference
---

`cursor-bundle/kg/bin/build_error_codes.py` → `error:` nodes + `throws` edges
(1,863 codes / 5,162 sites on the 2026-08-07 build).

## What is branch truth, and what is not

| Fact | Source | Trustworthy as |
|------|--------|----------------|
| throw site `file:line`, class, severity | Java parse of the live checkout | **branch truth** — carries repo/branch/sha |
| `ctx_keys` (EC placeholders) | `executionContext.put(...)` calls preceding the throw | branch truth |
| message template | Redis db2 `localmfi_<code>_en-in` | **runtime only** — no repo carries it |

Numeric error templates are seeded outside every repo. `notification_message` holds 2,593
alphanumeric codes (`LON-ACT-001`) and **zero** numeric ones. So a template is never
evidence about a train — `kg error` labels it `RUNTIME, not branch truth`.

## Resolution rules (do not weaken)

- Constants resolve **file-local → qualified `Class.CONST` → repo → globally unambiguous**.
  `MFIConstants.INVALID_ERROR_CODE` is `LOS-0016` in both los and reporting; a name with two
  values in one repo stays unresolved rather than picked.
- Codes are **not** 6-digit-only: `\d{3,6}` and `LOS-0016` / `COL-012` shapes are all real.
  The first cut assumed 6 digits and silently under-indexed by ~800 codes.
- 511 dynamic throws (`new NovopayFatalException(errorCode)`) and 728 unresolved tokens are
  **skipped**, never mapped to a plausible code.

## Gates that keep it honest

- `scripts/lib/error_index_drift_gate.py --strict` — re-reads every indexed site against
  source; wired into `ship-loop-gate.sh`. Currently 0 stale of 5,162.
- `kg_validate.py` fails closed on dangling `throws` edges — `refresh_cases.py` once deleted
  1,850 error nodes while keeping their edges and every other count still looked healthy.
- `scripts/lib/error_diag_gate.py` derives `kg why` diagnostics from evidence only and
  refuses to emit without a registry case.

## Rebuild

```bash
bash cursor-bundle/kg/bin/build.sh --force        # after a branch switch or new throws
python3 scripts/lib/error_index_drift_gate.py --strict
```

Related: [[feedback_kg_error_first_hop_not_grep]]
