# LMS-DEFECT — GAP-062 writeoff PrepaymentApproppriation NPE

**Status:** **WONT_TRACK** (2026-07-31) — `loanWriteoff` not developed / not live; do not QA-retest.

## Disposition

- User 2026-07-31: writeoff LAN transaction itself is not working / not developed → stop tracking GAP-062 and related writeoff defects.
- Code: `896c02a56` (appropriation EC normalize) **reverted** by `131e57a2f` on `origin/mfi_integration_v3.4.2.4`.
- Gaps SoT: GAP-062 marked **WONT_TRACK / Out of scope**.

## Historical (archive only)

Orch keys vs `PrepaymentApproppriationProcessor` reads caused NPE on writeoff path; catalogue `LOAN_WRITE_OFF`/`FINAL_WRITE_OFF` also absent locally (132223). Reopen only if product delivers writeoff.
