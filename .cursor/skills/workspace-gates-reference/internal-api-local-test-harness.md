<!-- VERBATIM archive of former alwaysApply `.cursor/rules/internal-api-local-test-harness.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Internal API — local HTTP test harness (mandatory on money-tier close)

Many accounting APIs (e.g. `individualChildLoanForeclosure`, `childLoanForeclosure`) run in **production only via internal orchestration** (`CallInternalOrchestrationWithoutJsonProcessor`, event queue). They never hit the service gateway in prod.

**Local `ntest auto` / workspace-close** posts through the **HTTP gateway**, which **requires** JTF templates or fails with **13003** (request) / **13005** (response).

## When this rule applies

Any money-tier ship / workspace-close for an `apiName` that:

- Has orchestration in `deploy/application/orchestration/*.xml`, **and**
- Has **no** `deploy/application/templates/request/product/{apiName}_requestTemplate.json` on the release branch, **and**
- Is invoked internally in prod (grep `CallInternalOrchestrationWithoutJson`, `api_name`, `loan_account_events_queue`, `callInternalAPI`).

## Ship checklist (same PR / push batch as processor change)

| Layer | Repo / path | Action |
|-------|-------------|--------|
| **JTF request** | `trustt-platform-accounting/deploy/application/templates/request/product/{apiName}_requestTemplate.json` | Clone sibling API template (e.g. `loanPrepayment`); rename root key to `apiName`. **Commit in service repo** — not workspace-only. |
| **JTF response** | `.../response/product/{apiName}_responseTemplate.json` | Clone sibling; rename root key; match success `code` from orchestration XML. |
| **Registry** | `scripts/testing/registry.json` | Add `type: flow` case with `"api": "{apiName}"` → e2e shell script. |
| **E2E script** | `scripts/testing/<domain>/{api}-e2e.sh` + payload builder `.py` if needed | Setup SQL, replay reset, call API. |
| **Local SQL** | `scripts/sql/setup/local_setup_*.sql` | Only if local DB gaps (PTC, product config). Wire from `scripts/bin/*-local-setup.sh`. |

## Do not

- Leave templates as **untracked** workspace files — they belong in **accounting-v2** (or owning service) deploy templates.
- Assume prod breakage — missing templates only block **direct HTTP** tests; internal prod path is unaffected.
- Skip templates because `ntest` sent `{}` — add registry **flow** case, not bare `ntest auto` without payload.

## Verify before workspace-close

```bash
test -f trustt-platform-accounting/deploy/application/templates/request/product/{apiName}_requestTemplate.json
ntest run <registry.flow.case>
```

## Reference

- Internal entry: `ChildLoanForeclosureProcessor` → `individualChildLoanForeclosure`
- Gateway parse: `JSONHelperForRequestResponse` → **13003** / **13005**
- Registry example: `foreclosure.individual_child`
