---
name: feedback_pending_ship_gc_no_sticky
description: >-
  Pending ship GC drops clean+pushed zombies; sticky money no longer forever.
  2026-07-31.
---

# Pending ship — no forever sticky money

## Old (broken) policy

Harness/docs push skipped money close but **kept** service paths in
`.pending-ship-work.json` “for the next product push”. Combined with merge-only
`register_paths`, pending became a zombie bag → autopilot/ship-loop re-ran huge
suites on unrelated work.

## New policy

`scripts/lib/pending_ship_gc.py` — **keep only unshipped work**:

| State | Action |
|-------|--------|
| dirty working tree for path | KEEP |
| clean but `origin/branch..HEAD` touches path | KEEP (unpushed) |
| clean and fully on origin | DROP |
| scratch / missing | DROP |

Wired into: `register_pending_ship`, `ship_push_gate` (harness skip), `session_ship`
auto-close, `stack-doctor`, CLI `bash scripts/bin/pending-ship-gc.sh`.

Disable: `PENDING_SHIP_GC=0`. Dry: `PENDING_SHIP_GC_DRY=1` or `--dry-run`.

## Agent rule

Do not re-introduce “keep sticky money across harness pushes”. Dirty/unpushed
money still blocks product ship via normal close — not via zombie pending.
