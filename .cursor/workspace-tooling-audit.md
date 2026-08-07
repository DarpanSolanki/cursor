# Workspace tooling audit — "looks green but isn't" defects

**Date:** 2026-08-08. **Scope:** read-only audit of the KG (`cursor-bundle/kg/`), the rule-router
hook, `scripts/testing/corroborate.py`, `scripts/testing/platform_api_map.py::called_by`, and a
spot-check of generated `.cursor/*.md` coverage docs. No accounting code or data touched; no
registry/KG files modified. Every claim below was run and its output captured in this session.

This session (prior to this audit) already fixed four defects of this class:
`scripts/lib/accounting_flow_domains.py::bucket()` substring-matched domain hints (penal counted
toward `interest_accrual`), `loanAccountAssetCriteriaJob`'s fixture drove NPA suspense negative
without an assert catching it, a batch-assert-timing bug, and a silent-skip on deferred asserts
when a wait step was skipped (see `git log -1 accounting_flow_domains.py`, commit `cd792c3`). The
brief was to hunt for more of the same pattern elsewhere. Findings below, ranked by how much they
would mislead an agent that trusted them.

---

## Deliverable 1 — defects found

### 1. [HIGHEST] `called_by` reverse-caller index silently drops ~52% of real callers

**Tool:** `scripts/testing/platform_api_map.py::callers()`, lines 274–293.

**Mechanism — wrong denominator.** The KG has a `rel='calls'` edge type populated by
`cursor-bundle/kg/bin/build_internal_calls.py`, which exists specifically to capture Java
`.callInternalAPI(...)` / `putLocal("api_name", ...)` dispatch that orchestration XML cannot see
(its own docstring: *"Orchestration XML only lists top-level processors. Many money paths dispatch
a child Request at runtime... Without these edges, `kg why`/`kg orient` miss nested processors"*).
It emits two edge shapes:

```
processor:{bean} -calls-> request:{repo}/{apiName}                    # every dispatch site
request:{parent} -calls-> request:{repo}/{apiName}                    # only when the bean's
                                                                        # own orchestration parent
                                                                        # is known
```

`callers()` reads only the second shape:

```python
# scripts/testing/platform_api_map.py:285-288
for src, dst in con.execute(
        "SELECT src_id, dst_id FROM edges WHERE rel='calls' "
        "AND src_id LIKE 'request:%' AND dst_id LIKE 'request:%'"):
```

Measured against the live `kg.db`:

```
rel='calls' total:                        1571
request:%  -> request:%  (counted):        747
processor:% -> request:%  (DROPPED):       811   (51.6%)
  of which the calling processor has NO
  orchestration parent at all (100% invisible,
  not even reachable via the parent-fallback): 456
```

**Reproduction — a named money API:** `postTransaction` is the accounting engine's core posting
entry point. `build_internal_calls.py` found direct dispatches into it from batch item writers,
e.g.:

```
processor:SGToDisbursementCancellationIWriter -calls-> request:trustt-platform-accounting/postTransaction
processor:SGToManualJournalEntriesIWriter     -calls-> request:trustt-platform-accounting/postManualJournalEntry
```

`postTransaction`'s recorded `called_by` in `cursor-bundle/flow-test/platform_api_map.jsonl` has
24 entries and **zero** `SGTo*` writers:

```python
$ python3 -c "...print(len(cb)); print([x for x in cb if 'SGTo' in x])"
called_by count: 24
SGTo* present: []
```

An agent changing `postTransaction`'s contract and grepping the map for callers would not see
these batch-writer callers at all — the exact failure mode `no-flow-break-impact-check.md` and
`api-contract-safety.md` exist to prevent.

**Blast radius — everywhere `called_by` is trusted as ground truth:**

| File | How it uses `called_by` |
|---|---|
| `.cursor/rules/api-contract-safety.mdc` (always-on-scoped for `**/*.java`, `**/*.xml`) | Tells agents to run `python3 scripts/testing/platform_api_map.py --api <name>` as **the** way to answer "who calls this" — the first line of its mandatory pre-change checklist |
| `.cursor/platform-api-map.md:37-38` (generated doc, read every session it's cited) | States outright: *"`callers` answers the first line of the contract-safety checklist — find all callers — without a fifteen-repo grep."* This actively discourages the correct fallback (grep) in exactly the case it's needed |
| `scripts/testing/platform_lookup.py:90` | Surfaces the same undercounted list under `bullet("called by", ...)` for any `platform_lookup.py <api>` call |
| `scripts/lib/test_platform_surface.py::CallerIndexTest.test_the_hottest_contracts_record_their_callers` (line ~199-207) | The only automated guard on this field, and it is **presence-only**: `assertTrue(by[api]["called_by"], ...)`. `postTransaction`'s list is non-empty (24 entries), so this test is green despite the 50%+ undercount — it can only catch total loss, never partial loss |
| `scripts/testing/loan_flow_worklist.py::eod_chain()` (lines ~92-97) | Reuses the identical `rel IN ('calls','calls_api') AND src_id LIKE 'request:%'` filter to compute EOD/BOD reachability depth for `.cursor/loan-flow-coverage-plan.md`. Any flow reached only via a batch-writer dispatch (not a request→request edge) is undercounted as "not in the EOD chain," which can misrank it in the coverage worklist |
| `scripts/testing/platform_api_map.py:477-479` ("hot APIs" ranking, top 15 by caller count) | Ranks by the same undercounted list — an API whose only callers are batch writers would rank as having 0 callers |

**Contrast — the primary KG tool does not have this bug.** `kg impact <api>`
(`cursor-bundle/kg/bin/kg.py::cmd_impact`, recursive CTE at ~line 513) walks `e.src_id` for
`e.dst_id=<target>` over **all** edges with no `src_id LIKE 'request:%'` filter, so it correctly
surfaces `processor:*` callers. The bug is isolated to the generated `platform_api_map.py` report,
not the KG's own impact walker — but the workspace's rule text (`api-contract-safety.md`) points
agents at the weaker tool by name.

**Proposed fix (not applied — for review):** in `callers()`, additionally union edges where
`src_id LIKE 'processor:%'`, resolve each processor to its owning request(s) via the existing
`invokes` edge (the same `proc_to_reqs` map `build_internal_calls.py` already builds internally —
it just isn't persisted), and for processors with no orchestration parent, attribute the caller as
the processor/batch-writer bean itself (e.g. `"<repo>/writer:SGToDisbursementCancellationIWriter"`)
rather than dropping it silently. Update `test_platform_surface.py::CallerIndexTest` to assert a
count floor for a known-batch-called API (e.g. `postTransaction` must include at least one `SGTo*`
or `writer:` caller), not just non-empty.

---

### 2. [HIGH] The substring-bucketing bug fixed in `accounting_flow_domains.py` recurs in two more domain-classifiers that don't reuse the fix

The session's prior fix added `_path_hint_matches()` (token-boundary aware: a hint must not be a
mid-token substring — `interestaccrual` must not match inside `penalinterestaccrual`) and wired it
into `accounting_flow_domains.py::bucket()`. Two other domain classifiers read the *same kind* of
`path_hints`/`api_hints` data but never call that helper:

**2a. `scripts/lib/lms_service_domains.py::detect_service_domains()`, lines 24-38.**

```python
for p in low_paths:
    if any(r in p for r in repos):       # raw substring, repo_hints
        matched = True; break
    if any(h in p for h in phints):      # raw substring, path_hints
        matched = True; break
```

This selects which non-money-service impact cases are mandatory for a ship
(`resolve_lms_service_cases()`, called from the ship-gate case resolver). Several `path_hints` in
`scripts/lib/lms_service_domains.json` are bare identifier fragments with no slash boundary:
`'origination'`, `'disbursementsync'`, `'requestforward'`, `'collectionloanrepayment'`,
`'bulkcollection'`, `'updatebusinessdate'`, `'batchschedule'`, `'infra-'`, `'util-platform'`. Any
changed-file path or diff blob that happens to contain one of these as a mid-word substring
(the `joined` fallback path even concatenates *all* changed paths into one string and substring-
matches against that) pulls in that service's impact cases. The practical direction here is
**over**-inclusion (extra required tests), which is the safe failure direction for a ship gate —
but it is the identical unguarded pattern, and an unguarded prefix like `'infra-'` can match paths
that have nothing to do with `trustt-platform-lib`.

**2b. `scripts/lib/registry_proposals.py::draft_from_ship()`, line 69.**

```python
hints = [h.lower() for h in (d.get("path_hints") or []) + (d.get("api_hints") or [])]
if any(h and h in blob for h in hints):
    domain = name
    break
```

This reads `accounting_flow_domains.json`'s domain hints — the exact data whose consumer
(`bucket()`) was just fixed — but reimplements its own raw-substring match instead of importing
`_path_hint_matches`. It labels the domain for an **auto-drafted regression-pin proposal**
(`registry_proposals.json`), which matters because `accounting-full-flow-gate.md` cites
`registry_proposals.py ratchet`, and `10-quality-gates.md` Gate D-acceptance ratchets money
domains (`death_foreclosure`, `disbursement`, `repayment`, `foreclosure`, `interest_accrual`)
**per domain, growth-only**. A proposal mislabeled into the wrong domain (e.g. the same
penal-vs-`interest_accrual` collision the fix's CHANGELOG entry names) credits growth to a domain
that didn't actually gain coverage, while the domain that should have gained a case shows nothing.

**Proposed fix (not applied):** both call sites should `from accounting_flow_domains import
_path_hint_matches` and use it in place of `in`.

---

### 3. [MEDIUM] `corroborate.py` — most of its 14–16 checks are presence/freshness only, and the one true ratchet silently adopts a corrupted baseline

Read in full (`scripts/testing/corroborate.py`). Breakdown of what each check actually verifies:

| Check | What it actually asserts | Can it catch a content/logic bug downstream? |
|---|---|---|
| `_kg_state_ok` | substring `"STALE"`/`"FRESH"` in a report file it does not regenerate | No — inherits whatever blind spot `kg fresh` has (see deliverable 3) |
| `_hooks_ok` | specific hook command substrings present in `hooks.json` | No — structural only |
| `_intel_layers` | per-layer output file mtime not stale (`sync_engine.is_stale`) | No — freshness, not content |
| `_hub_fresh` | `workspace-intelligence-state.md` mtime < 1h | No |
| `_registry_ok` | `n > 0` cases in `registry.json` | **No — literally the presence-only pattern this session's fix targeted** (`40-knowledge-upkeep.md` explicitly calls this out: "Presence-only is not an assert") |
| `_test_map_ok` | `n > 0` rows in `test_map.jsonl` | No |
| `_money_proof_gaps` / `_platform_proof_gaps` / `_domain_coverage` | ratchet — direction only (see below) | Only in the direction "did the *count* get worse," not "is the count honest" |
| `_orch_index_ok` | JSON parses, has a `count` key | No |
| `_pending_ship` | file existence flags | No |
| `_ops_state` | mtime < 24h | No |
| `_bus_recent_failures` | latest event per case isn't a failure | Yes, for cases that actually ran and were recorded — but see its own two self-documented prior bugs in the source comments (stale-window counting, skipped-case-never-clears) |
| `_registry_gap_sample` / `_autopilot_verify` (full mode only) | informational count / subprocess exit code | Partial |

The one mechanism that is a genuine ratchet, `_gap_ratchet()` (lines 200-236), has a structural
weakness: it auto-writes the *current* measured value as the new baseline whenever the count
improves (lines 229-231):

```python
if gaps < baseline:
    baseline_path.write_text(json.dumps({"gaps": gaps}) + "\n", encoding="utf-8")
    return Check(name, True, f"{gaps} APIs with gaps (improved from {baseline})")
```

`gaps` is computed from `test_coverage.jsonl`, which is itself built from the domain-bucketing
machinery in finding #2. If a bucketing bug *undercounts* gaps (exactly what the fixed
`bucket()` bug did — it inflated coverage by folding dead penal APIs into `interest_accrual`,
which is the same shape as *reducing* the visible gap count), the ratchet has no external
ground truth to compare against — it only compares this run's number to the last-recorded
number. A generator bug that makes the count look better gets locked in as the new floor on the
very next green run, and the ratchet can never flag it, because "gaps improved" is exactly what
the mechanism is designed to reward.

**Net effect:** none of `corroborate.py`'s checks would have moved on any of the four defects
already fixed this session (verified explicitly in deliverable 3) — a `14/14` or `16/16` headline
from this tool proves file/row/mtime presence, not the correctness of what those files say.

---

### 4. [Checked, clean] `.cursor/hooks/rule-router.py`

Read in full. Uses `fnmatch.fnmatch()` per-glob with an explicit `_variants()` expansion that
handles minimatch's "`/**/` matches zero directories" case (`a/**/*.java` also matches
`a/X.java`), and the `dir/**` / `**/x` special-cases both preserve the trailing `/` boundary
(`rel.startswith(g[:-2])` keeps the slash, so `trustt-platform-los/**` cannot match
`trustt-platform-los2/...`). Verified with direct tests:

```python
fnmatch.fnmatch('trustt-platform-los2/src/main/java/Foo.java', 'trustt-platform-los/**')  # False
fnmatch.fnmatch('foo/repository/x.java', '**/repository/**/*.java')                        # False (needs an extra dir level)
fnmatch.fnmatch('a/repository/b/x.java', '**/repository/**/*.java')                        # True
```

No substring-vs-boundary bug found here — this is a clean bill, recorded so it isn't re-audited
from scratch later. (Note for future audits: fnmatch's `*` matches `/` too, since fnmatch has no
path-separator awareness — this is a latent design quirk shared with the whole glob approach, not
a defect in this file specifically; it hasn't produced an observed false match in the current
`manifest.json` because every glob's literal segments are anchored by real `/` characters.)

---

## Deliverable 2 — every place `called_by` is read as ground truth (blast radius for finding #1)

```
scripts/testing/platform_api_map.py:410,414,442,477,479   # generator: builds + ranks "hot APIs"
scripts/testing/platform_lookup.py:90                      # `platform_lookup.py <api>` "called by" bullet
scripts/lib/test_platform_surface.py:199-215                # CallerIndexTest — presence-only guard
.cursor/rules/api-contract-safety.mdc                        # tells agents to use this tool for "find all callers"
.cursor/platform-api-map.md:16,37-59                         # generated doc; claims it substitutes for a grep
scripts/testing/loan_flow_worklist.py (eod_chain, ~92-97)   # reuses the same request:%-only filter pattern
cursor-bundle/flow-test/platform_api_map.jsonl              # the data file itself (regenerated artifact)
```

Whoever fixes the undercount should re-run `scripts/lib/test_platform_surface.py` and
`scripts/testing/loan_flow_worklist.py` afterward — both will change output once `called_by` is
complete, and the EOD-chain depth numbers in `.cursor/loan-flow-coverage-plan.md` will likely grow
(more flows become reachable), which is the direction that ratchet expects.

---

## Deliverable 3 — would `kg.py validate` / `fresh` / `integrity_check` have caught any of the four session defects?

**No, on all four.** Read `cursor-bundle/kg/bin/kg_validate.py` in full (81 lines) and
`_drift_check()` in `kg.py` (~line 1041). What they actually check:

- **`kg validate`** (→ `kg_validate.py`): `kg.db` file exists and is >100KB; SQLite `PRAGMA
  integrity_check` (physical page corruption only); `nodes`/`edges` row counts above fixed floors
  (3000 / 10000 — a coarse size guard, not a content guard); one FTS query runs without asserting
  on its result; a check for dangling `throws` edges (added after a prior incident where a rebuild
  step deleted error nodes but kept their edges); `stats.json` node count within 5% of the live DB
  count. Every one of these is structural presence/consistency, not semantic correctness.
- **`kg fresh`** (→ `_drift_check()`): compares each watermarked repo's git SHA / dirty-file set
  against what's live on disk. It answers "does the KG reflect the current checkout," not "is what
  the KG derived from that checkout correct."

None of the four defects fixed this session — `bucket()`'s substring domain match, the
`loanAccountAssetCriteriaJob` fixture driving NPA suspense negative unassert-ed, the
batch-assert-timing bug, or the silent-skip on deferred asserts when a wait step is skipped —
change any repo's git SHA, corrupt the SQLite file, or move node/edge counts outside a 3000/10000
floor. All four are downstream **Python logic bugs in code that consumes the KG's edges**, and the
KG's own health-check machinery has no mechanism that inspects derived-fact correctness at all —
only structural presence and "does this describe the code that's on disk." The same is true of
this audit's own new finding (`called_by` undercount): `kg validate`/`fresh` are both green on the
current checkout right now, while `called_by` is silently wrong for `postTransaction` and hundreds
of other APIs.

The nearest thing the workspace has to a semantic guard is `test_platform_surface.py` — but as
finding #1 shows, its guard for exactly this bug is presence-only and passed throughout. There is
currently no automated check anywhere in the workspace that would fail if a domain-bucket or
caller-reverse-index silently mis-derived a fact while still producing a non-empty, structurally
valid result. That is the general shape of the gap: **structural health (row counts, SHA match,
file presence) is well-guarded; derived-fact correctness is guarded only by hand-inspection and
CHANGELOG entries recording each fix after the fact.**

---

## Summary ranking (most likely to mislead an agent that trusted it, most severe first)

1. **`called_by` / `platform_api_map.py::callers()`** — undercounts by ~52%, is explicitly cited
   by an always-on rule (`api-contract-safety.md`) and its own doc (`platform-api-map.md`) as a
   grep replacement, and its only automated guard is presence-only. Highest severity: it is
   pointed to *by name* as authoritative for the exact safety check ("find all callers") that
   protects money-path contract changes.
2. **`lms_service_domains.py` / `registry_proposals.py` substring domain matching** — same class
   as the already-fixed `bucket()` bug, not yet ported to the token-boundary-safe helper. Lower
   severity than #1 because the ship-gate consumer (2a) fails safe (over-inclusion), but 2b
   (auto-drafted proposal domain labeling) can misattribute ratchet growth across enforced money
   domains.
3. **`corroborate.py`** — not a single false claim, but a systemic one: its headline score cannot
   move on the class of bug this audit was asked to hunt for, because 10+ of its ~14 checks are
   presence/freshness, and its one real ratchet (`_gap_ratchet`) has no external ground truth and
   silently absorbs generator undercounts as the new floor.
4. **`kg validate`/`fresh`** — confirmed structural-only by design; not a defect so much as a
   documented gap in what "the KG is healthy" is allowed to mean. Recorded here so it's not
   mistaken for a completeness guarantee it never made.
5. **`rule-router.py`** — audited, clean.
