---
name: pr-review
description: >-
  Performs proof-backed, zero-speculation GitHub pull-request reviews with fresh
  SHA provenance, principal-architect domain checks, confidence, and test evidence.
  Use when asked to review or audit a PR, pull request, PR URL, or owner/repo#number.
---

# Principal-architect PR review

Review pull requests without changing the user's working tree or external systems.
Produce both a full evidence report and a concise response for the developer. Optimize
for zero false positives: silence or a precise evidence request is better than an
incorrect suggestion.

## Inputs

- Required: GitHub PR URL or `owner/repo#number`.
- Optional: Jira key, target environment, review depth (`quick` or `full` — **agent reading depth only**; `pr-review.sh` has no `--depth` flag), and explicit review focus.
- Optional mutation request: post a PR review or Jira comment. Treat this as a separate, explicit action after presenting the draft.

If the PR or target environment is ambiguous, collect metadata first and ask only for the missing decision that changes the verdict.

## Safety defaults

1. Run `bash scripts/bin/pr-review.sh <PR> [--jira KEY] [--env ENV]`.
2. Use the collector's GitHub API evidence without checking out the PR.
3. Never switch, reset, clean, stash, or overwrite the user's working tree.
4. If source checkout, compilation, or local bots are needed, create an isolated temporary worktree from fetched immutable SHAs. Do not reuse a dirty service checkout.
5. Read-only is the default. Never call `gh pr review`, `gh pr comment`, `gh issue comment`, Jira mutation tools, push, merge, or close commands unless the user explicitly requests that mutation after seeing the draft.
6. Never expose authentication tokens, cookies, credentials, or secret-valued environment variables in artifacts or reports.
7. Collector output remains under `scripts/scratch/pr-review/` until the review consumes it. Remove only the task's own scratch directory at task end.

## Non-negotiable proof contract

Every review must identify:

- PR URL and number.
- Repository.
- Base branch and immutable base SHA.
- Head branch and immutable head SHA.
- Collection timestamp.
- Requested environment and Jira key, or `not provided`.
- Branch/train status: `ALIGNED`, `SCOPED`, `STALE`, or `MIXED`.
- Evidence actually run: diff inspection, source reads, CI checks, build, tests, runtime/API/DB verification.
- Evidence not run and why.

Every finding must contain:

- Severity: `BLOCKING`, `MAJOR`, `MINOR`, `NIT`, or `QUESTION`.
- Confidence: `CONFIRMED`, `SUSPECTED`, or `NOT-VERIFIED`.
- Exact evidence: `file:line` from source at the collected head SHA or a CI/test/log ID tied to that SHA; add a requirement citation when relevant.
- Observable failure mode and affected path.
- Smallest actionable change or question.

Only `CONFIRMED` items are findings or directives. `SUSPECTED` items are developer
questions, never instructions. `NOT-VERIFIED` items belong under missing evidence,
not Findings. Never infer runtime behavior from memory, generic best practice, the
knowledge graph, a bot, compilation, or code shape alone.

If proof is insufficient, say:

`I lack evidence to confirm <claim> — need <specific artifact>.`

Do not propose a fix until the defect and its value/control source are confirmed.

## Review pipeline

### 1. Prove freshness before inspection

Use the collector output:

- `metadata.json`: PR identity, base/head refs and SHAs, state, author, labels, counts.
- `files.json`: complete changed-file inventory.
- `commits.json`: ordered commit inventory.
- `checks.json`: check runs and combined commit statuses.
- `diff.patch`: reviewed patch.
- `freshness.json`: initial/final PR metadata plus fetched `refs/pull/N/head` and base-ref agreement.
- `provenance.json`: collector version, read-only guarantees, collection status.
- `errors.json`: partial collection failures.
- `manifest.json`: SHA-256 hashes for review artifacts.

The collector must fetch `refs/pull/N/head`, resolve the current base ref, collect the
PR diff, and re-fetch metadata/refs after collection. Require all recorded base/head
SHAs to agree. Refuse stale local refs, wrong branches, mixed trains, incomplete
freshness evidence, or a changing PR; verdict is `NOT VERIFIED` with provenance.
Read unchanged context through the GitHub contents API with `ref=<head_sha>` or an
isolated worktree at that SHA; never cite the user's mutable checkout.

Immediately before the final report, run the collector again and compare base/head
SHAs. If either changed, discard the prior review and restart from the new artifact
set. Never combine evidence from different SHAs.

### 2. Align Jira, branch, train, and environment

- Resolve the Jira Reported version to the expected `upstream/mfi_integration_vX.Y.Z` train when Jira is provided.
- For each affected repository, record `branch@sha`. Use `cursor-bundle/brain/runbooks/mixed-train-matrix.md`.
- Treat feature/WIP or cross-service mixed trains as scoped, not production truth.
- Mark `STALE` if the reviewed base is not the expected current base.
- Mark `MIXED` if a cross-service conclusion depends on incompatible trains.
- Do not approve when required provenance is stale, mixed, or unavailable.

### 3. Inventory scope and requirements

- Enumerate all commits and changed files before summarizing.
- Run `python3 scripts/lib/infer_ship_apis.py --classify <path>` as needed to identify workspace/service/money tier and apiNames.
- Trace each Jira acceptance criterion or PR requirement to changed code and verification evidence.
- Flag unrelated files, generated noise, missing migration/release artifacts, or requirements without implementation.
- Separate developer statements into:
  - `Developer-reported` — PR/Jira/QA statement only.
  - `Independently verified` — confirmed at the collected head SHA or by tied CI/runtime evidence.
  - `Open` — contradicted, untested, or missing proof.
- Never mark “handled”, “fixed”, or “tested” resolved from the author's statement alone.

### 4. Apply domain lenses

Apply all relevant lenses; write `N/A` with a reason only when the diff proves the lens is out of scope.

- **Correctness:** null/default branches, boundary values, error paths, ordering, concurrency, transaction boundaries.
- **Contracts:** additive HTTP/JTF/Kafka/ExecutionContext behavior; all callers; deploy skew.
- **Money/state:** orchestration to processor to DB/posting, exact amounts/components, audit fields, partial failure, reversal, replay, dirty/pre-existing state.
- **SQL/data:** reuse-query ladder, callers, native SQL semantics, soft-delete/audit predicates, indexes and `EXPLAIN`, migration plus production manual DDL pack.
- **Performance/scale:** N+1, calls in loops, repeated scans, unbounded reads, chunk/day multipliers, cache miss behavior.
- **Idempotency:** deterministic keys, CAS/locking, retries, duplicate messages, partial commits, status monotonicity.
- **Security/privacy:** authorization, tenant isolation, injection, path traversal, unsafe deserialization, logging of secrets/PII, dependency/config exposure.
- **Operations:** observability, correlation keys, retry/reconciliation, rollback, release order, configuration compatibility.
- **Regression:** adjacent APIs/batches, existing registry cases, webapp-bound APIs, QA acceptance shape.

For accounting, Kafka, Redis, shared library, or multi-service changes, consult the matching workspace rules, `.cursor/gaps-and-risks-digest.md` (escalate to full `.cursor/gaps-and-risks.md` when GAP-id/area flagged), KG orientation, orchestration XML, and authoritative source. Known open High gaps in the changed path are verdict inputs.

### 5. Eliminate codebase-specific false positives

Before claiming missing, unused, unwired, leaking, or behavior-changing:

1. Widen search before absence: search definitions, aliases/constants, callers, XML/JTF,
   message-broker wiring, configuration, and sibling flows at the collected SHA.
2. Prove reachability: cite definition + caller + orchestration/consumer wiring.
3. Prove the actual value source: trace the getter/ExecutionContext key/DB column used
   at the decision or booking point; do not reason from a similarly named field.
4. Prove scope: trace `put` versus `putLocal`, local flags, copied contexts, and
   downstream readers before asserting overwrite or leakage.
5. Prove absence across the relevant repository scope before saying something does
   not exist. Otherwise ask a `SUSPECTED` question.

Use `.cursor/rules/10-quality-gates.mdc`, `darpan.mdc`,
`30-kg-discipline.mdc`, `10-quality-gates.mdc`, and
`api-contract-safety.mdc`; these rules are authoritative and are not duplicated here.

### 6. Use automated reviewers as secondary lenses

- Bugbot and Security Review are optional and never determine the verdict by themselves.
- Run them only when their local-diff contract can be satisfied in an isolated worktree at the collected base/head SHAs.
- Independently verify every bot finding against the reviewed SHA and source.
- Record bot failures or unavailable execution as missing evidence, not as a clean result.

### 7. Compile and test proportionately

- Existing CI is evidence only when tied to the reviewed head SHA.
- For local compilation/tests, use an isolated worktree and record command, exit code, and head SHA.
- Workspace tier: syntax/validators, KG validation, `ntest validate`.
- Service tier: service build plus relevant health/API evidence.
- Money tier: build plus the actual registry flow and value-level DB assertions for every touched money table; include dirty-state and webapp-bound verification when applicable.
- Compile-only, HTTP 200, batch `COMPLETED`, simulation-only, or row-presence checks do not prove money correctness.
- Do not `APPROVE` a money-path change from logic review alone. Numeric acceptance
  remains `NOT VERIFIED` until real-flow evidence proves exact values, dirty-state
  behavior, and the QA acceptance shape. Follow
  `feedback_qa_acceptance_not_subset_verify.md` and
  `feedback_real_flow_db_write_validate.md`.

### 8. Adversarially falsify every candidate

Before emitting the report, attempt to disprove each candidate against source at the
head SHA and any tied runtime evidence:

- look for an earlier guard, alternate caller/path, scoped context, configuration,
  rollback/retry behavior, or test that invalidates the concern;
- verify cited lines still exist at the final collected SHA;
- drop disproved items;
- downgrade unprovable items to a clearly marked question or missing evidence;
- never send speculative fixes or unverified suggestions to the developer.

The report must state: `Self-review: attempted to falsify each finding against the reviewed head; unproven items were dropped or downgraded.`

## Verdict taxonomy

Choose exactly one:

- **APPROVE** — requirements are covered; no blocking finding; base/head/environment provenance is aligned; required CI/build/tests passed for the reviewed head SHA; money changes have runtime flow and value-level evidence, or the PR is demonstrably non-money.
- **COMMENT** — no correctness blocker is evidenced, but there are non-blocking improvements or questions. Required approval evidence is otherwise sufficient.
- **REQUEST CHANGES** — an evidenced defect, contract break, security issue, money/idempotency risk, unrelated dangerous scope, or missing mandatory test/release artifact must be fixed before merge.
- **NOT VERIFIED** — evidence is insufficient or inconsistent: inaccessible PR, stale/mixed provenance, changing head SHA, unavailable required environment, missing runtime/DB proof, or blocked build/tests. This is not an approval.

When both a blocking defect and missing verification exist, use `REQUEST CHANGES` and list the missing evidence separately. Never downgrade an evidenced blocker to `NOT VERIFIED`.

## Final evidence report

```text
PR Review: <title>
Verdict: <APPROVE | COMMENT | REQUEST CHANGES | NOT VERIFIED>
Confidence: <CONFIRMED | NOT-VERIFIED>

Provenance
- PR: <url>
- Repository: <owner/repo>
- Base: <branch>@<sha>
- Head: <branch>@<sha>
- Environment: <value | not provided>
- Jira: <key | not provided>
- Train status: <ALIGNED | SCOPED | STALE | MIXED> — <evidence>
- Collected: <UTC timestamp>
- Freshness: <base/head/ref agreement and final re-fetch result>

Scope and requirements
- Commits/files: <counts and concise inventory>
- Requirement trace: <criterion → code → evidence>
- Out of scope: <items>

Claim status
- Independently verified: <claim → file:line/check/log>
- Developer-reported: <claim → source; not independently proven>
- Open: <claim/question → exact missing evidence>

Findings
1. [<severity>][CONFIRMED] <file:line or check> — <failure mode>. <smallest action>

Questions
1. [QUESTION][SUSPECTED] <evidence> — <neutral question; no directive>

Verification
- PASS: <command/check/API/DB evidence tied to head SHA>
- FAIL: <evidence>
- NOT RUN: <reason>

Residual risks
- <risk or none>

Self-review: attempted to falsify each finding against the reviewed head; unproven items were dropped or downgraded.
```

Omit Findings or Questions when empty. Do not omit provenance, claim status,
verification, or self-review.

## Developer response

Keep this plain, concise, and pasteable:

```text
Review verdict: <verdict>
Reviewed: <repo PR> base <sha> → head <sha>; freshness <status>.

Confirmed asks:
- [<severity>][CONFIRMED] <file:line/check> — <action>

Questions:
- [QUESTION][SUSPECTED] <evidence> — <question>

Independently verified: <claims and evidence>.
Developer-reported only: <claims or "none">.
Still open / NOT VERIFIED: <specific missing artifacts or "nothing">.
Self-review: attempted to falsify each finding; unproven items were dropped or downgraded.
```

Use 3–7 actionable points at most. Do not mention internal agent/IDE mechanics. Do not claim QA-ready or production-safe from logic review alone.
The developer response may contain only `CONFIRMED` asks and clearly marked
`SUSPECTED` questions.

## Mutation gate

After producing both outputs, stop. If the user explicitly asks to post:

1. Show the exact final text and target PR/Jira.
2. Confirm the collected head SHA still matches.
3. Use the relevant GitHub/Jira tool once.
4. Report the resulting URL.

Without that explicit request, external mutations are forbidden.
