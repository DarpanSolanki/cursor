# Discovery inbox (auto-captured — triage into gaps-and-risks.md)

Agents append here via `scripts/bin/brain-gap-capture.sh`. **Not** production gap registry until reviewed.


## DISC-20260804-092649 — flowtest.invariants_universal was vacuous; de-vacuumed gate surfaces 1381 FC-settlement AIR imbalance on fixture LAN 6000137440
- **Captured:** 2026-08-04T09:26:49Z
- **Risk (provisional):** High
- **Evidence:** run_universal_invariants_gate.py passed baseline=snapshot_invariants(lans) taken moments before, so every baseline-delta invariant was neutralised and the money-tier case could never fail. Fixed to baseline=None (absolute). First strict run: inv FC settlement AIR FAIL 6000137440 |D-C|=1381.000000 refs=['261319e97c3233fe74e27bc19acad2fc6b653','251340004ab4fd8aa4d5b849b70366b8900c1'] (TDPQA-72 392164 class). Code contract (double-entry: debit==credit) is not in question — an imbalance means bad rows in the LOCAL fixture, which accumulates across runs. Action: reseed LAN 6000137440, do NOT weaken the assert. Trust code over local DB state.
- **Triage:** add to `.cursor/gaps-and-risks.md` if confirmed; else mark dismissed below.

