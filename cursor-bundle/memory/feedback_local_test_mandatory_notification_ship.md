# Local test mandatory — SP-308 missed it

**Standing (2026-07-23):** User called out that SP-308 L0/L1 was pushed without local ntest despite the harness existing. Valid.

## What went wrong (two layers)

1. **Agent process:** service repos were `git push`ed after `compileJava` only — skipped `ntest` / `workspace-close` ship-loop for the notification change.
2. **Workspace gaps:**
   - No registry case for `loanInstallmentDueNotificationJob`
   - Ship infer invented `disburseLoan` → wrong E2E
   - `wait_batch_job.sh` required param `job_time` but jobs persist `time` → false STARTING timeout

## Fixes

- Registry: `batch.loan_installment_due_notification`, bounce sibling, `config.notification_sms_throughput`
- Ship path-trigger → those cases (not health-only / not disburse)
- `wait_batch_job.sh`: match by `run_started` create_time window; accept `time`/`job_time`
- Assert script for SMS threads/maxPoll

## Rule

Never push accounting/notifications code with compile-only. Ship-loop must resolve to the **matching** ntest case and PASS it this session.
