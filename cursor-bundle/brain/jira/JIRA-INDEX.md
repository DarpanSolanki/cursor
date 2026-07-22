# JIRA flow graph — index (verified)

Machine: [`jira-flow-graph.json`](jira-flow-graph.json)

**Accounting:** `mfi_integration_v3.7.1@f45dbe3bd` (DeathForeclosureInsuranceWriter.java INT-180 uncommitted).

Every api link has `Request name=` in orchestration. Every commit is ancestor of HEAD or a HEAD-equivalent SHA for the same fix. Code proofs cite files on this checkout.

## Reopen playbook

1. Ticket → `apis` / `key_commits` / `test_cases` below.

2. `git merge-base --is-ancestor <sha> HEAD` in accounting-v2.

3. `ntest run <test_case>` when listed.

4. Confirm writer/processor still matches `code_proof`.

## Tickets

| JIRA | Domain | APIs | Tests | HEAD commits | Status |
|------|--------|------|-------|--------------|--------|
| **SDCP-10199** | `death_foreclosure` | `deathForeclosureInsuranceJob`, `loanDeathForeclosure` | `dcf.group_parent_last_child_e2e` | `f45dbe3bd`, `e919e3b33`, `66e830670` | verified_this_session |
| **SDCP-10227** | `disbursement` | `disburseLoan` | `disbursement.quick` | `068247cc9`, `b78517980` | verified_this_session |
| **SDCP-11016** | `foreclosure` | `fetchLoanForeclosureSimulationDetails` | `dpic.foreclosure_bpd_growth`, `dpic.foreclosure_sim` | `f5c4e0a25` | verified_this_session |
| **SDCP-11048** | `prepayment` | `loanPrepayment` | `dpic.loan_prepayment_billed_dpi_e2e` | `1b34dee4b` | verified_this_session |
| **SDCP-11058** | `foreclosure` | `loanPrepayment`, `childLoanForeclosure`, `individualChildLoanForeclosure` | `foreclosure.shg_bpi_parity` | `4acc7036d4` | verified_this_session |
| **SDCP-11012** | `dpi` | `dpiAccrualCalculation` | `dpic.shg_parent_child_parity` | `f42f5b117` | verified_this_session |
| **SDCP-11030** | `dpi` | `dpiAccrualCalculation` | — | `412f4d03e` | verified_this_session |
| **SDCP-10295** | `read_inquiry` | `getLoanAccountSummaryDetails` | — | `82cb142e7` | verified_this_session |
| **SDCP-9301** | `death_foreclosure` | `loanDeathForeclosure`, `deathForeclosureInsuranceJob` | `dcf.group_parent_last_child_e2e` | — | behaviour_on_HEAD_historical_ticket |
| **SDCP-9844** | `death_foreclosure` | `loanDeathForeclosure`, `deathForeclosureInsuranceJob` | — | — | behaviour_on_HEAD_historical_ticket |

### Code proofs

- **SDCP-10199:** DeathForeclosureInsuranceWriter.sumPendingComponentOnOrBefore + lastActiveChild INT/DPI from parent pending (L1253,L1340-1374); e2e PASS×2; DB parent INT/PRIN/DPI pending=0
- **SDCP-10227:** CallBankAPIForDisbursementProcessor + ChildDisbursementLoanEventsQueueSync on HEAD; SHAs ancestors
- **SDCP-11016:** FetchLoanForeclosureSimulationDetailsProcessor uses DpiForeclosureBrokenPeriodService.calculateTillForeclosureDate; orch Request verified; HEAD sha f5c4e0a25
- **SDCP-11048:** ValidateFinalPrepaymentProcessor.fetchForeclosureAmount adds getBilledDpiAmountToBePaid+getBpdAmountToBePaid; HEAD sha 1b34dee4b (ancestor); changelog 167d0942db same patch not ancestor
- **SDCP-11058:** ChildLoanForeclosureProcessor BPI uses getDistributedAmountEqually(parent) like foreclosure_fee (any N); ntest foreclosure.shg_bpi_parity unit PASS; product children sum to parent BPI
- **SDCP-11012:** DpiGroupLoanAccrualAdjustService parent vs sum(children) adjust on HEAD; registry case api=dpiAccrualCalculation; HEAD sha f42f5b117
- **SDCP-11030:** DpiAccrualCalculationBatchService.resolveSliceInstallment + resolveAdmissionOverdueDate on HEAD; 412f4d03e ancestor. .cursor/changelog claims e2e PASS — registry has no sdcp-11030 tag (test link omitted)
- **SDCP-10295:** GetLoanAccountSummaryDetailsProcessor interest_original=getBilledInterestAmount; outstanding=billed-(paid+waived+writtenOff); 82cb142e7 ancestor. orch: verify Request
- **SDCP-9301:** DFC core series — behaviour in DeathForeclosureInsuranceWriter on HEAD; historical SHAs may not be ancestors; orch+writer verified this session
- **SDCP-9844:** DFC settle/waive series — same writer on HEAD; orch+writer verified this session

### Session-proven reopen symptoms

- **SDCP-10199:** parent CLOSED with INT pending>0 after last-child DFC (pre-fix: due 2025-09-01 pending 180) — PASS ntest run dcf.group_parent_last_child_e2e (2026-07-10 twice)

### Blocked / omitted (concrete)

- Remote QA/prod DB — not used (local only)
- SDCP-11030: no registry case tagged sdcp-11030 — test link omitted (code+SHA verified)
- SDCP-10295: no registry e2e case — code+SHA verified only
- Cross-service LOS/payments contracts on mixed trains — not claimed

## Agent usage

```bash
python3 cursor-bundle/kg/bin/kg_validate.py
python3 cursor-bundle/kg/bin/kg.py flow deathForeclosureInsuranceJob
ntest run dcf.group_parent_last_child_e2e
python3 -c "import json;print(json.load(open('cursor-bundle/brain/jira/jira-flow-graph.json'))['nodes'][0])"
```

