---
name: feedback-kg-error-first-hop-not-grep
description: An error code in the report means run kg_error FIRST — measured 1958 greps vs 7 KG calls over 18 sessions; kg_error is ~160 tokens, cheaper than one grep
metadata:
  type: feedback
---

Darpan, 2026-08-07: *"still lot of code traversing was done and database schema was checked,
what is the point of having everything up to date in KG… the tools created are not getting
used."*

He was right, and it was measurable. Across 18 session transcripts (7,069 tool calls):

| | calls | share |
|---|---:|---:|
| KG MCP | 7 | 0.1% |
| raw `grep`/`rg` on source | 1,958 | 27.7% |
| `kg.py` CLI | 144 | 2.0% |

14 of 18 sessions never called the KG at all.

**Why:** it was not only discipline. The KG could not answer what an RCA starts from —
`kg error 132168` returned "not seen in any case" because `error:` nodes came only from
CHANGELOG mentions (13 codes). Fixed by `build_error_codes.py` (1,863 codes / 5,162
source-derived throw sites).

## How to apply

- **An error code in the report → `kg_error` before anything else.** It returns every throw
  site with `file:line` + branch, the ExecutionContext keys the message template needs, the
  runtime template, and prior shipped fixes — for **~160 tokens**, below a single targeted
  grep. Grepping for a code first is the most common waste in this workspace.
- `NOT_INDEXED` is a **coverage statement**, never "this code is unused". It names the three
  causes (dynamic throw / other branch / config-raised). Verify with the grep it prints.
- Templates are labelled `RUNTIME, not branch truth` — no repo carries numeric error
  templates, they live in Redis db2 only. Never present one as train-verified.
- `kg flow` hides `dummyProcessor` by default and marks `⚠throws:N`; `--raw` for the
  unfiltered chain. Nothing is dropped from the index, only from the view.

## Why the gates alone did not cause this

Two HARD STOPs fire on almost every money task (`[MIXED]` trains, `[PROVISIONAL]` KG), and
both say *do not conclude from the KG*. That is compliant behaviour producing the wrong
outcome: a knowledge layer warned-off by default can never become the primary path. The
fix was to make the KG worth reaching for and to route to it explicitly — not to weaken the
verify step, which still stands (`30-kg-discipline.md` Gate C).

Related: [[reference_error_code_index]] · [[feedback_ship_test_autonomy_change_map]]
