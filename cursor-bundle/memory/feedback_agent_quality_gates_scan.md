---
name: feedback_agent_quality_gates_scan
description: "Standing scan (2026-06-29): root cause classes for wrong RCA, stale code, weak testing, flow confusion — mandatory gates in agent-quality-gates.mdc"
metadata:
  node_type: memory
  type: feedback
---

## Why sessions still go wrong (evidence from this workspace)

### 1. Git / branch (highest blast radius)

- **Mixed workspace:** e.g. accounting on `mfi_integration_v3.3.1.2` while actor/lib/webapp on `feature/delayed_payment_interest` — KG and grep read **wrong code** for cross-service calls.
- **Manifest overrides vs disk:** `.cursor/git-branch-manifest.json` may say accounting → DPI feature; actual checkout may differ. **Disk wins** — run `bash scripts/bin/git-workspace-status.sh` every session.
- **RCA without fetch:** `git fetch origin && git fetch upstream` before mapping stack traces to deployed branch (`feedback_fetch_latest_before_checking_code.md`).
- **Provisional KG:** 8+ WIP repos → `kg watermark` is provisional; do not treat as release contract without verifying release base.

**Gate:** Read `.cursor/git-workspace-state.json` + `python3 cursor-bundle/kg/bin/kg.py watermark` before any money/RCA work. If task is NOT DPI → `sync_branches_v2.sh <integration_train>` OR state explicitly which repos are out of scope.

### 2. Flow confusion (accounting)

| Confused pair | Disambiguate by |
|---------------|-----------------|
| Death FC (`loanDeathForeclosure`) vs child FC (`individualChildLoanForeclosure`) vs loan FC | apiName + `accounting_flow_domains.json` → `death_foreclosure` vs `foreclosure` |
| Outstanding/claim (death-date snapshot) vs GL BLD/UNBLD split (approve posting) | Same writer, **different job_time anchors** — see `system_brain/flows/death_foreclosure.md` |
| Claim form staging vs insurance batch APPROVE | Staging uses death date only; approve may need reporting-date billing **before** split when reporting ≫ death |
| DPI accrual/booking/billing vs interest accrual | **Different jobs** — DPI sibling is interest accrual job shape, not DPD (`feedback_mirror_proven_sibling_exactly.md`) |
| Simulation / workbook vs live LAN E2E | Dev JIRA: "scenario model" unless `ntest` fired real API on that LAN |

**Gate:** `python3 scripts/lib/accounting_flow_domains.py` is not a CLI — use `bash scripts/bin/accounting-flow-coverage.sh` + `kg flow <apiName>` + **read orchestration XML** for the request.

### 3. KG misuse

- KG = structure + opt-in precedents — **not** runtime DB, not deployed branch truth.
- `kg orient` without `kg validate` / `kg fresh` → stale spine on branch switch.
- Skipping orchestration XML after `kg flow` → wrong processor order (e.g. DCF billing sync).

**Gate:** `kg-safety-and-consultation.mdc` order: MEMORY → CANONICAL-MAP → validate → orient → **XML + processors** → db-local.

### 4. Testing gaps (honest matrix)

| Claim | Requires |
|-------|----------|
| Scenario Pass | `ntest run <case>` or documented script with PASS output **this session** |
| Workbook aligned | Formula/simulation or read-only SQL — label as such in JIRA |
| Live LAN Pass | Fresh API/batch on that LAN after reset — not simulation |
| Ship close | `workspace-close.sh --from-pending` — not `compileJava` alone |

Coverage debt (2026-06-29): `read_inquiry` 91 gaps, `write_ops` 47, `batch_other` 31 — do not assume read APIs are proven because `accounting.read_smoke` exists (local DPI fields often fail).

### 5. Session entry (compressed)

```
git-workspace-status.sh → kg watermark → workspace-intelligence-state.md
→ classify task domain (DPI? death FC? disburse?)
→ align branches OR declare scope
→ kg orient <api> → read orch XML → db-local (if RCA)
→ before-test → ntest (honest result labels)
```

Related rules: `agent-quality-gates.mdc`, `dpi-feature-branch-gate.mdc`, `kg-safety-and-consultation.mdc`, `minimal-fix-impact-gate.mdc`.
