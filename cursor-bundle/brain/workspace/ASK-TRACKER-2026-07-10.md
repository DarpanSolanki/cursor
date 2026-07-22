# Ask Completeness Tracker — 2026-07-10

**Parked INT-180 off 3.7.1 (2026-07-10T12:51:06Z):** ASK-057 → DEFERRED; GAP-074 remains open.

**Last implementer update:** 2026-07-10T18:25+05:30  
**User decision:** INT-180 / last-child parent INT-DPI under-settlement kept as **open GAP-074**. Fix parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8`; `mfi_integration_v3.7.1` @ `f45dbe3bd` — **do not merge/push to 3.7.1** until QA/prod case + discuss.
**INT-180:** **DEFERRED** / park branch only — ASK-057 not DONE for production

## Gate status (must be clear before "done")

| Gate | Status | Evidence |
|------|--------|----------|
| ASK-057 INT-180 commit+ship | **DEFERRED** | Parked `61278d5f8` on `fix/sdcp-10199-parent-int-dpi-last-child-dfc`; 3.7.1 @ `f45dbe3bd`; GAP-074 open |
| ASK-H01..H07 | **DONE** | hooks/ship/docs/SHA/gaps/scripts/nps — see JSON evidence |
| ASK-041 QA confidence | **DEFERRED** reopen | Cannot claim production-sure while GAP-074 open / fix not on 3.7.1 |
| ASK-053 Harmony | **DONE** (WARN-only) | H01–H07 green; H08 mixed trains documented |
| ASK-027C/E | **OPEN** (backlog WS-023/024) | Explicitly deferred — not harmony/INT-180 blockers |
| ASK-048 suite | **DONE** | release_cases filled; WS-022 for dedicated e2e |
| ASK-H10 capture | **DONE** (WARN) | sources.jsonl capture; footprint_builder FTG gap remains |
| ASK-042/043 PR/push | **IN_PROGRESS** | No upstream push (user); INT-180 must stay off 3.7.1 |

## Status counts (implementer update)

| Status | Count |
|--------|------:|
| DONE | 63 |
| IN_PROGRESS | 2 |
| OPEN | 2 |
| DEFERRED | 2 |
| BLOCKED | 0 |

Machine twin: [`ask-tracker-2026-07-10.json`](ask-tracker-2026-07-10.json) (authoritative statuses after this update).

---

---

## Summary counts (this scan)

| Status | Count |
|--------|------:|
| DONE | 54 |
| IN_PROGRESS | 11 |
| OPEN | 4 |
| BLOCKED | 0 |
| **Total distinct asks** | **69** |

**Omitted asks:** none inventoried as missing from this checklist.  
**Harmony FAIL items:** H01,H03–H07 **DONE**; H02 **IN_PROGRESS** (workspace-close); H08–H10 **DONE**.

---

## A. SDCP-10199 RCA / fix / ship (Jul 7–9) — historical thread asks

| ID | Verbatim intent (compressed) | Acceptance criteria | Evidence | Status |
|----|------------------------------|---------------------|----------|--------|
| ASK-001 | Analyse SDCP-10199 on QA6; Vikram latest comment; find gap after “fixed” claims | RCA with evidence (code+QA DB/logs); gap named | Parent transcript RCA turns; JIRA SDCP-10199 | DONE |
| ASK-002 | Branch deployed is 3.4.2.1 | Analysis scoped to 3.4.2.1 train | User stated; fixes landed on `mfi_integration_v3.4.2.1` | DONE |
| ASK-003 | Use Accounting.txt job ran 03:19 PM | Correlate job time to Vikram observations | Log path used in session | DONE |
| ASK-004 | Explain RCA simply; why iterations failed; why Vikram observations remain | Plain-language root cause | Transcript explanations | DONE |
| ASK-005 | Compare to 3.3.1.1 “fixed” comment / code | Diff 3.3.1.1 vs deployed 3.4.2.1 behaviour | Session branch compare | DONE |
| ASK-006 | Do not zero overdue; only future INT waived; explain unpaid vs settled | Correct waive/settle semantics documented + coded | Writer + brain runbook `sdcp-10199-group-parent-last-child-dfc.md` | DONE |
| ASK-007 | Why PRIN paid=0; insurance should settle PRIN; explain every Vikram observation | Per-observation mapping; PRIN paid not waived | Changelog + e2e asserts PRIN waived=0 | DONE |
| ASK-008 | PRIN settle / INT waive only; check QA3/QA4 DFC cases | Cross-env confirmation (QA4 down → QA3) | QA3 checks in session | DONE |
| ASK-009 | Implement L1 + local simulate; fix once-and-for-all; no reopen | L1 in code + local e2e | `DeathForeclosureInsuranceWriter.java`; `dcf.group_parent_last_child_e2e` | DONE (3.4.2.1 era); see ASK-040 for 3.7.1 reopen |
| ASK-010 | Fix on **3.4.2.1** not 3.4.2.3; test; push | Branch correct; push to origin 3.4.2.1 | Changelog Jul 7–8 ship notes | DONE |
| ASK-011 | Testing: correct posting, amounts, DB updates; no assumptions/guesses | DB-backed asserts; no NOT VERIFIED laziness on local | `group_dfc_dev_proof.sql`; e2e PASS logs | DONE (local); ASK-038 for QA6 gap |
| ASK-012 | Wire local stack (Kafka up); bypass non-mandatory; last batch job success; do not stop | Local DCF stack + batch success | `ensure_dcf_local_stack.sh`; payments/notifications stubs; `dcf-local-stack.md` | DONE |
| ASK-013 | Payments port wrong → check DB; bypass payments if needed **without code hacks** | Config/stub method, not production code edits for test | `local_payments_stub.py` (not writer hacks) | DONE |
| ASK-014 | SHG has children (not “JLG-only” confusion); mature testing suite + platform integration docs | Naming/group semantics + suite maturation | Rename to `group_parent_last_child_*`; `dcf-local-stack.md` | DONE (A+B+D); C/E still OPEN as ASK-027 |
| ASK-015 | Full e2e again; 100% code-wise sure all observations fixed | Green e2e + asserts for Vikram obs | `scripts/scratch/dcf_e2e_verify2.log` PASS | DONE (local fixture); QA remaining obs → ASK-039 |
| ASK-016 | LAN backup / restore for retest | Fixture backup/restore | `dcf_fixture_backup.py` | DONE |
| ASK-017 | Proceed; fix testing suite | Suite updates landed | registry `dcf.group_parent_last_child_e2e` | DONE |
| ASK-018 | Final report: GL, amounts, business flow | Final verification report in session | Transcript final report turns | DONE |
| ASK-019 | Product clarification: parent↔child sync; create LANs, 1-1 repayment, then DFC to separate data vs bug | Controlled fixture path proving sync | Local group e2e fixture path | DONE |
| ASK-020 | Review `payRemainingOverduePenalThroughDeathDate` — genuine vs hack | Verdict + keep/remove | Session analysis | DONE |
| ASK-021 | Backup LAN then proceed | Backup exists | `dcf_fixture_backup.py` + LAN 6000137433 | DONE |
| ASK-022 | Fix only genuine issues; else create data and confirm stitch | Genuine fixes only | Core INT/PRIN path fixes (not clamp-only) | DONE |
| ASK-023 | If 10199 fixed without breaking other DFC → push; else more scenarios; then upgrade workspace/knowledge | Push + knowledge | 3.4.2.1 push + later 3.7.1 work | DONE (push); workspace upgrade continues ASK-041+ |
| ASK-024 | Sync origin↔upstream on 3.4.2.1 and push | Origin/upstream aligned for release train | Session git ops Jul 8 | DONE |
| ASK-025 | Minimal lines / trim fix; then push | Minimal L1 | Trimmed writer changes | DONE |
| ASK-026 | Release confidence: no hacks; all Vikram obs; FE amounts; enrich JIRA concise with proofs | JIRA comment + fields updated | JIRA enrichment session Jul 8 | DONE |
| ASK-027 | Maturation plan: user said **go A+B+D** (not C/E) | A rename; B registry; D local-stack doc | A: `group_parent_last_child_dfc_local_e2e.py`; B: registry case; D: `dcf-local-stack.md`. **C** helpers extract + **E** coverage still OPEN | PARTIAL → C/E tracked as ASK-027C / ASK-027E |
| ASK-027C | Extract reusable test helpers (payments stub, actor seed, staging cleanup, batch wait) | Helpers under `scripts/testing/lib/` reused | Not found as shared lib extraction | OPEN |
| ASK-027E | Group-flow smoke: child repayment fan-out, CLB stuck (read-only first) | Registry cases exist | Not present | OPEN |
| ASK-028 | JIRA skill: no internal/branch info; human developer language | Skill upgraded + JIRA rewritten | `jira-fix-update` skill updates in session | DONE |
| ASK-029 | Fix mistaken direct push to `mfi_release_v3.4.2.1`; process = integration → release | Process corrected / PR path fixed | Session Jul 8 git process fix | DONE |
| ASK-030 | PR integration→release still shows already-merged changes — explain/fix | Understood duplicate-diff; process clarified | Session | DONE |
| ASK-031 | JIRA aitdp % / remarks wrong (“used cursor”) | Fields corrected | Session JIRA update | DONE |
| ASK-032 | Special notes: many QA LANs corrupted / unsynced parent-child | Special notes on JIRA/release | Session | DONE |
| ASK-033 | Short email: fix released to QA; local e2e; QA LAN caveat | Email drafted | Session | DONE |
| ASK-034 | 100% code-wise working? Dev test proof in JIRA | Proof with DB details | `group_dfc_dev_proof.sql` + JIRA | DONE |
| ASK-035 | Start actor/notification/masterdata/api-gateway for webapp proof | Services started | Session ops | DONE |
| ASK-036 | Webapp login double-call | Diagnosed/fixed or explained | Session | DONE |
| ASK-037 | Parent LAN 6000137433 negative PRIN paid — analyse; genuine fix at source (not generic clamp) | Core fix (not clamp in generic class); retest; push | L1 at source; clamp rejected | DONE |
| ASK-038 | Why webapp 7993 schedule row; asset classification not updating — fix + test + push | Asset classification fixed + retest | Session Jul 8 push | DONE |
| ASK-039 | QA asked DFC transaction details in JIRA comment (table) | Tabular txn comment on JIRA | Session | DONE |
| ASK-040 | Vikram still open observations on 3.4.2.1; logs Accounting (1).txt; QA6 DB; why local missed; fix; retest; push | Gap in local coverage closed; fix pushed; remaining QA obs addressed or honestly scoped | Jul 9–10 fixes; ASK-041 QA remaining two obs | DONE (code push path); confidence ask ASK-041 |

---

## B. Jul 10 — merge / 3.7.1 / workspace upgrade (active)

| ID | Verbatim intent | Acceptance criteria | Evidence | Status |
|----|-----------------|---------------------|----------|--------|
| ASK-041 | Asking QA to test remaining two SDCP-10199 observations — are we sure? | Honest confidence with local proof + known gaps | User deferred INT-180 ship; **GAP-074 open** | **DEFERRED** — reopen when QA/prod case |
| ASK-042 | Resolve PR #7774 conflicts upstream; steps to complete merging | Conflicts resolved; merge steps documented/executed | User pointed `DeathForeclosureInsuranceWriter`; local merge strategy discussed | IN_PROGRESS — confirm PR state with evidence |
| ASK-043 | Merge `mfi_release_v3.6.1` + work locally; PR origin→upstream `mfi_integration_v3.7.1` | Clean PR path to 3.7.1 | Accounting on `mfi_integration_v3.7.1@f45dbe3bd`; INT-180 on park branch only | IN_PROGRESS — **do not merge INT-180** |
| ASK-044 | Confirm forward-merge: 3.4.2.1/2/3 fixes present on 3.7.1 | `merge-base --is-ancestor` for key SHAs | `e919e3b33`, `66e830670`, `425472cab` = ANCESTOR of HEAD | DONE |
| ASK-045 | Full re-analysis of DFC/group parent flow on 3.7.1 | Orch+writer+e2e re-verified on 3.7.1 | Runbook + e2e PASS×2; INT-180 RCA | IN_PROGRESS — uncommitted INT-180 |
| ASK-046 | Update/enrich scripts, KG, hooks, full workspace; close gaps/stale/wrong understanding; **do not stop until done** | No stale banners; KG FRESH; scripts match 3.7.1; gaps closed | Partial: KG FRESH; many docs updated; hooks FAIL (ASK-H01); gaps dual-home FAIL (ASK-H05) | IN_PROGRESS |
| ASK-047 | Maintain JIRA worked-on memory for reopen | Canonical index + reopen playbook | `cursor-bundle/brain/jira/JIRA-INDEX.md` + `jira-flow-graph.json` (9 nodes) | DONE (artifact exists); honesty vs “19 tickets” → ASK-H03 |
| ASK-048 | Enhance testing suite; analyse each flow/API suite; update per new code | Registry/domain coverage updated for 3.7.1; failing e2e fixed | `dcf.group_parent_last_child_e2e` PASS; **12/19 domains thin** (no release_cases) | IN_PROGRESS |
| ASK-049 | Smart JIRA↔flow graph (not flat list); reopen playbook | Graph with domains/apis/edges + playbook | `jira-flow-graph.json` nodes+edges; playbook in INDEX | DONE (graph quality); expand coverage still OPEN under ASK-048 |
| ASK-050 | Workspace upgrade for **ALL** accounting flows (not only some); self-improve/self-upgrade | All domains in `accounting_flow_domains.json` scanned; files/processes updated | 19 domains mapped; 12 thin/empty release_cases | OPEN |
| ASK-051 | Do not assume/guess when creating KG/scripts/tests/hooks; **validate KG** | `kg validate` + `fresh` PASS; no guessed edges | `kg validate` OK; `kg fresh` FRESH (this scan) | DONE (KG); ongoing discipline for new artifacts |
| ASK-052 | Verify maximally (code+DB); little scope for lazy NOT VERIFIED | Claims backed by orch/code/DB/ntest | E2e+DB for 10199; harmony still flags SHA mislabels | IN_PROGRESS |
| ASK-053 | Monitor subagent: no fuckups; code/JIRA/git/testing synced in harmony | Harmony report GREEN | Harmony **NOT GREEN** (2026-07-10 ~18:00) | BLOCKED — see ASK-H* |
| ASK-054 | Check super-agent + all autonomous/self scripts; maximize workspace setup | Inventory + fix broken wiring; CLIs work | Skills/CLIs exist; hooks/bootstrap/nps_app_log broken | IN_PROGRESS |
| ASK-055 | Do not scope to one JIRA — all workspace / all repos if required — perfect | Workspace-wide, multi-repo | Implementer expanding; mixed trains FAIL | OPEN |
| ASK-056 | Tracker agent so multiple asks not omitted | This tracker MD+JSON maintained | `ASK-TRACKER-2026-07-10.md` + `.json` | DONE (created this turn) |
| ASK-057 | INT-180 on 3.7.1: last-child parent overdue INT pending — fix + e2e green + **commit/ship** | Writer fix committed; e2e PASS; **production ship** | Parked: `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8`; GAP-074 open; 3.7.1 tip `f45dbe3bd` without fix | **DEFERRED** — do not merge to 3.7.1 until QA/prod discuss |

---

## C. Harmony FAIL acceptance items (mandatory — from harmony monitor)

Harmony overall: **WARN-only pending H02 ship-close** (H01/H03–H07 closed by gap-closure 2026-07-10). Mark DONE only with evidence.

| ID | Harmony FAIL | Acceptance criteria (DONE only if all true) | Evidence now | Status |
|----|--------------|-----------------------------------------------|--------------|--------|
| ASK-H01 | **Hooks wiring** — `afterFileEdit` → ship-path | `.cursor/hooks.json` → `after-ship-path-edit.sh`; executable; pending registers | L20 `after-ship-path-edit.sh`; L39 `post-commit-ship-test.sh` | DONE |
| ASK-H02 | **Ship pending honesty** | Commit + `workspace-close --from-pending` until `ship_push_gate --satisfied` | Writer committed `61278d5f8`; pending-ship present; ship-loop-passed absent until close | IN_PROGRESS |
| ASK-H03 | **Changelog 19 vs 9** | Count matches graph (9) | Changelog “9 verified nodes”; `rg '19 tickets'` empty | DONE |
| ASK-H04 | **CHANGELOG SHA labels** | Every `3.7.1` **header** SHA is ancestor of HEAD | 0 bad primary headers vs `61278d5f89` | DONE |
| ASK-H05 | **Gaps dual-home** | SoT declared; money rows synced | SoT=`.cursor/gaps-and-risks.md`; **GAP-074** open/deferred both homes | DONE |
| ASK-H06 | **Missing bootstrap scripts** | Scripts exist or refs updated | `workspace-bootstrap.sh` + `install-user-cursor-gates.sh` wrappers present | DONE |
| ASK-H07 | **nps_app_log** | Ops state non-empty app log | `nps_app_log` defined; ops-state app path set; agent-ops fallback hardened; WS-009 done | DONE |

### Harmony-related WARN (track, not FAIL-only)

| ID | Item | Acceptance | Status |
|----|------|------------|--------|
| ASK-H08 | Mixed git trains | Documented scope OR trains aligned | DONE — `runbooks/mixed-train-matrix.md` |
| ASK-H09 | Thin accounting domains (12) | ≥1 release_case **or** backlog ID | DONE — WS-019/020/025–034 inventory_gap_only |
| ASK-H10 | capture-flow / money footprint DFC | Footprint captured or deferred | DONE — `sources.jsonl` capture + `capture-flow.sh` fid fix |

---

## D. Implementer gate (must satisfy before “done”)

```text
[x] ASK-044 DONE (forward-merge)
[ ] ASK-057 INT-180 production ship — **DEFERRED** (GAP-074; parked on `fix/sdcp-10199-parent-int-dpi-last-child-dfc` @ `61278d5f8`; do not merge to 3.7.1 until discuss)
[x] ASK-H01, H03–H07 DONE with evidence (gap-closure)
[ ] ASK-H02 ship-close
[ ] ASK-046/048/050 not left OPEN without explicit BLOCKED+reason
[ ] ASK-053 Harmony re-audit GREEN or WARN-only after close
[x] ASK-056 tracker updated (this scan)
[ ] workspace-close / autopilot end
```

**Forbidden claim:** “SDCP-10199 INT-180 fixed in production” / “sure for QA on residual INT” while **GAP-074** is open or ASK-057 is **DEFERRED**. Do not merge `61278d5f8` onto `mfi_integration_v3.7.1` without user discuss after QA/prod case.

---

## E. Cross-check — sibling agents (this scan)

| Agent | Role | Observed | Impact on checklist |
|-------|------|----------|---------------------|
| Implementer `c02bf016…` | Full upgrade + INT-180 | Parked `61278d5f8` on `fix/sdcp-10199-parent-int-dpi-last-child-dfc`; 3.7.1 @ `f45dbe3bd` | ASK-057 → **DEFERRED**; GAP-074 open |
| Harmony `ae96213e…` | Audit | Was NOT GREEN ~18:00 | H01–H07 mostly closed by gap-closure |
| Gap-closure (this) | Unowned FAILs | hooks/docs/memory/train/capture/kg validate+orient | H01,H03–H10 DONE; H02 close next |

---

## F. Machine-readable twin

See `cursor-bundle/brain/workspace/ask-tracker-2026-07-10.json` (same IDs/statuses).

---

*Tracker is living — re-scan and update statuses when implementer lands evidence. Never mark DONE without paths.*
