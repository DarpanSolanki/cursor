<!-- VERBATIM archive of former alwaysApply `.cursor/rules/flow-cross-learn.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Flow cross-learn (mandatory)

When **any** flow test fails, or you discover a gap while making another flow pass:

1. **Record** — `bash scripts/bin/test-learn.sh --api <apiName> --kind gotcha --text "..."` (or `ntest learn`)
2. **Bus** — `cross_learn.record_test_result` / learning_bus (ntest does this on fail; disburse sanity on suite fail)
3. **Fix upstream** — if disburse broke DPI certify, fix `disburse_loan_sanity.py` + `disburse-quick.sh`, not only the downstream script
4. **Reuse** — extend existing scripts (`run_disburse_demo.sh`, `eod_milestones_from_loan.py`, `dpi-sanity.sh`); do not add parallel wrappers
5. **Hygiene** — scratch under `scripts/scratch/<task>/`; no orphan markdown

Hooks: `.cursor/hooks/post-ntest-intel-sync.sh` captures PASS (push) and FAIL (test-learn).

Skills: `super-agent` (`learn`, `sync`), `workspace-self-improve` (backlog drain).

Fresh LAN policy: disburse new loan per scenario; do not SQL-patch one LAN to pass unrelated smokes (exception: intentional replay/idempotency tests).
