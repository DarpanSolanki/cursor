# DCF local stack — death foreclosure insurance e2e

Local harness for `deathForeclosureInsuranceJob` and group parent last-child closure (SDCP-10199). Source of truth for bootstrap: `scripts/dcf_sanity/ensure_dcf_local_stack.sh`.

## Quick start

```bash
# Full registry flow (stack + e2e)
ntest run dcf.group_parent_last_child_e2e

# Or direct
bash scripts/dcf_sanity/run_group_parent_last_child_dfc_e2e.sh
```

## Service / port map

| Component | Port | Role |
|-----------|------|------|
| Kafka | 9092 | Required — accounting message broker consumers |
| YugabyteDB | 5433 | `mfi_accounting`, `mfi_batch`, `mfi_actor`, `mfi_masterdata` |
| Accounting | 8002 | `deathForeclosureInsuranceJob`, loan closure postings |
| Masterdata | 8014 | Internal API routing (via `dpi_ensure_masterdata`) |
| Actor | 8001 | Customer lookup for insurance outbound (via `dpi_ensure_actor`) |
| Payments stub | 8594 | `scripts/dcf_sanity/local_payments_stub.sh` — not full payments service |
| Notifications stub | 8015 | `scripts/dcf_sanity/local_notifications_stub.sh` — getMessage/sendEmail |

Accounting does **not** need a live payments `bootRun`. The stub answers `cancelCollections` on `:8594` so DCF paths that call payments complete locally.

## Bootstrap order (`ensure_dcf_local_stack.sh`)

1. Kafka listening on `:9092`
2. `local_setup_platform_master_service_endpoints.sql` — service endpoint rows
3. `dpi_ensure_masterdata` + `dpi_ensure_actor` (from `scripts/dpic/lib/dpi_demo_fixture.sh`)
4. `local_payments_stub.sh ensure` + `local_notifications_stub.sh ensure`
5. `local_setup_dcf_fixture_actor_customers.sql` — actor customer rows for insurance outbound
6. `local_setup_dcf_insurance_ptc_placeholders.sql` — PTC placeholder → IAD for insurance postings
7. Accounting restart/ensure (`novopay-service.sh`; skip full restart with `DCF_STACK_SKIP_ACCOUNTING_RESTART=1`)

## Message broker / batch

- Batch trigger: `scripts/testing/api-fire.py deathForeclosureInsuranceJob --batch --job-time <epoch_ms>`
- Approve reader scans `death_foreclosure_insurance_staging_details` by id window (`INBOUND_SUCCESS` rows)
- **Local quirk:** `glCBSIntegration` may log connection-refused after closure; loan can still reach `CLOSED`. E2e polls loan status, not only `batch_job_execution.status`.
- Batch status poll (when needed): `mfi_batch.batch_job_execution` joined to `batch_job_instance` by `job_name` + `create_time` epoch.

## Fixture / retest on same LANs

| Tool | Purpose |
|------|---------|
| `dcf_fixture_backup.py snapshot <parent_lan>` | One-time pristine backup (parent + all children) |
| `dcf_fixture_backup.py restore <parent_lan>` | Revert to pristine before re-run |
| `group_parent_last_child_dfc_local_e2e.py` | Auto snapshot on first run, auto-restore on later runs |

Env flags:

- `DCF_E2E_NO_SNAPSHOT=1` — skip backup/restore
- `DCF_E2E_RESTORE=1` — force restore at end of run
- `PARENT_LAN` / `CHILD1_LAN` / `CHILD2_LAN` / `DEATH_DATE` — fixed fixture; omit to auto-discover fresh product-70 group

Default synced fixture (registry): parent `6000137433`, children `6000137440` / `6000137441`, death date `2025-11-02`.

## Staging hygiene

Abandoned `INBOUND_SUCCESS` staging rows from prior runs can be re-picked by the approve reader (id-window scan). The e2e script quarantines other inbound rows before each approve. For manual runs, mark stale staging `COMPLETED` or use `cleanup_abandoned_staging` logic in `group_parent_last_child_dfc_local_e2e.py`.

Penal reconcile (fixture data only): `scripts/sql/setup/local_setup_dcf_fixture_penal_reconcile.sql` when billed PINT > accrued PINT on a test loan.

## Dev test proof (JIRA handoff)

After e2e Pass, run `scripts/dcf_sanity/group_dfc_dev_proof.sql` and paste outcomes into JIRA Dev Test Details (loan status, principal paid/waived/pending, posting amounts). See `.cursor/skills/jira-fix-update/SKILL.md` § Dev test evidence.

## Ship-loop wiring

Registry: `dcf.group_parent_last_child_e2e` (`type: flow`, `smoke_tier: money`).

`scripts/lib/accounting_flow_domains.json` → `death_foreclosure.impact_cases` includes this case so DCF code changes run it in the money-tier ship loop.

## Related

- Group parent/child sync: [`shg-jlg-children-missing.md`](shg-jlg-children-missing.md)
- SHG fan-out tables: [`../accounting/db-code-map/by-flow/shg-jlg-fanout.md`](../accounting/db-code-map/by-flow/shg-jlg-fanout.md)
- Scenario matrix metadata: `scripts/dcf_sanity/scenarios.json`
