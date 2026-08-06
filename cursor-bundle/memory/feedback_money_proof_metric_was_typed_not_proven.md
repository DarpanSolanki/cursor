---
name: money-proof-metric-was-typed-not-proven
description: Footprint 'verified' came from a CLI flag, not a run — 18 of 21 money footprints had no recorded run
metadata:
  type: feedback
---

Footprint 'verified' came from a CLI flag, not a run — 18 of 21 money footprints had no recorded run

**Why:** `capture-flow.sh` writes `status: verified` from `--verified`, with no link to any execution. The money-proof board could be turned green by appending lines. Meanwhile `ntest` had been emitting `test_pass`/`test_fail` per case all along and nothing consumed it.

**How to apply:** treat a 'verified' footprint as a claim, not proof. Check `python3 scripts/testing/run_evidence.py --api <apiName>` for a recorded run before citing coverage. When a coverage number needs to move, move it with a run — `footprint_evidence_gate.py` ratchets the unbacked count so it can only shrink. And before calling a money API RED, check the case applies to the checked-out train: `requires_paths` makes DPI cases skip off-train rather than fail. See [[reference-forward-merge-chain]].
