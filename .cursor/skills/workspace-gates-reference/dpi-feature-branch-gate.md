<!-- VERBATIM archive of former alwaysApply `.cursor/rules/dpi-feature-branch-gate.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# DPI branch gate (mandatory before code analysis)

**When the task mentions:** DPI, DPIC, delayed payment interest, dpiAccrual*, dpiBilling, DPI go-live, loan restructuring + DPI.

**Before grep, read processors, or trust `kg flow`/`cases`:**

1. Read `cursor-bundle/memory/reference_dpi_feature_branch.md`
2. Verify checkout matches the **task branch** (do not assume feature WIP):
   - **Default release train (harness / QA):** `trustt-platform-accounting` → **`mfi_integration_v3.7.1`** (HEAD must include booking fix `77921d275f`)
   - **Unmerged WIP only when task says so:** `feature/delayed_payment_interest` on accounting-v2 + initial-setup (+ webapp if UI)
3. `bash scripts/bin/kg-switch.sh` — KG watermark must match the branch under test
4. Optional: `git merge-base --is-ancestor 77921d275f HEAD` on accounting-v2 for 3.7.1 booking fix

**Never** conclude "field/API missing" from the wrong train (e.g. older `mfi_integration_*` without DPI fixes, or feature tip when task is 3.7.1).

**Mixed workspace** (webapp on feature, accounting on integration) → wrong analysis. Align branches first.
