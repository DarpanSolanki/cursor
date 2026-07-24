#!/usr/bin/env python3
"""CLB queue harness — dedupe poison REP_ACCT rows before childLoanEventProcessingBatchJob.

See cursor-bundle/brain/runbooks/clb-duplicate-rep-acct.md and
scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql.
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql", "-h", os.environ.get("YB_HOST", "localhost"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-v", "ON_ERROR_STOP=1", "-t", "-A",
]

DEDUPE_SQL = ROOT / "scripts/sql/adhoc/clb_dedupe_rep_acct_events_queue.sql"


def psql(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def psql_multi(sql: str) -> None:
    subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)


def pending_clb_queue_id(parent_account_id: int) -> str:
    return psql(f"""
SELECT id::text FROM mfi_accounting.loan_account_events_queue
WHERE parent_account_id = {parent_account_id}
  AND event_type = 'CLB' AND event_status = 'P' AND is_deleted = false
ORDER BY id DESC LIMIT 1;
""")


def count_members_with_dup_rep(queue_id: int) -> int:
    row = psql(f"""
SELECT count(*)::text FROM (
  SELECT m_ord FROM jsonb_array_elements(
    (SELECT data::jsonb FROM mfi_accounting.loan_account_events_queue WHERE id = {queue_id})
  ) WITH ORDINALITY AS m(m_elem, m_ord),
  jsonb_array_elements(m_elem #> '{{createLoanAccountRequest,disbursement_repayment_account_details}}') a(acc)
  WHERE COALESCE(acc #>> '{{purpose,0,code}}', '') = 'REP_ACCT'
  GROUP BY m_ord HAVING count(*) > 1
) d;
""")
    return int(row or "0")


def dedupe_clb_rep_acct_for_parent(parent_account_id: int) -> int | None:
    """Dedupe REP_ACCT in pending CLB data; clear filler_1 for batch retry. Returns queue id or None."""
    qid = pending_clb_queue_id(parent_account_id)
    if not qid:
        return None
    qid_int = int(qid)
    dup_before = count_members_with_dup_rep(qid_int)
    if dup_before == 0:
        psql_multi(f"""
UPDATE mfi_accounting.loan_account_events_queue
SET filler_1 = NULL, updated_on = NOW()
WHERE id = {qid_int} AND event_type = 'CLB' AND event_status = 'P' AND is_deleted = false;
""")
        return qid_int
    subprocess.check_call(
        [*PG[:-2], "-v", "ON_ERROR_STOP=1", "-v", f"queue_id={qid_int}", "-f", str(DEDUPE_SQL)],
        env=PG_ENV,
    )
    psql_multi(f"""
UPDATE mfi_accounting.loan_account_events_queue
SET filler_1 = NULL, updated_on = NOW()
WHERE id = {qid_int} AND event_type = 'CLB' AND event_status = 'P' AND is_deleted = false;
""")
    dup_after = count_members_with_dup_rep(qid_int)
    print(
        f"  CLB dedupe parent_id={parent_account_id} queue_id={qid_int} "
        f"members_with_dup_rep before={dup_before} after={dup_after}"
    )
    if dup_after > 0:
        raise RuntimeError(f"CLB dedupe failed: queue_id={qid_int} still has {dup_after} members with dup REP_ACCT")
    return qid_int


def max_batch_execution_id(job_name: str) -> int:
    row = psql(f"""
SELECT COALESCE(MAX(bje.job_execution_id), 0)::text
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = '{job_name}';
""")
    return int(row or "0")


def wait_batch_after(job_name: str, min_execution_id: int, timeout_s: int = 180) -> str:
    """Wait for a new batch_job_execution with id > min_execution_id (TZ-safe; no create_time epoch)."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = psql(f"""
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = '{job_name}'
  AND bje.job_execution_id > {min_execution_id}
ORDER BY bje.job_execution_id DESC
LIMIT 1;
""")
        if row == "COMPLETED":
            return row
        if row in ("FAILED", "STOPPED", "ABANDONED"):
            raise RuntimeError(f"batch {job_name} {row}")
        time.sleep(2)
    raise RuntimeError(f"batch {job_name} timeout after {timeout_s}s")


def wait_batch_by_start(job_name: str, started_epoch: int, timeout_s: int = 180) -> str:
    """Legacy wrapper: wall-clock start is unreliable vs timestamp-without-tz create_time.

    Prefer wait_batch_after(max_batch_execution_id) from fire sites. Kept for callers that
    only have a wall clock — compare create_time in session TimeZone (Asia/Kolkata).
    """
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        row = psql(f"""
SELECT bje.status
FROM mfi_batch.batch_job_execution bje
JOIN mfi_batch.batch_job_instance bji ON bji.job_instance_id = bje.job_instance_id
WHERE bji.job_name = '{job_name}'
  AND EXTRACT(EPOCH FROM (bje.create_time AT TIME ZONE current_setting('TimeZone')))::bigint
      >= {started_epoch}
ORDER BY bje.job_execution_id DESC
LIMIT 1;
""")
        if row == "COMPLETED":
            return row
        if row in ("FAILED", "STOPPED", "ABANDONED"):
            raise RuntimeError(f"batch {job_name} {row}")
        time.sleep(2)
    raise RuntimeError(f"batch {job_name} timeout after {timeout_s}s")


def quarantine_billing_portfolio(parent_account_id: int, child_account_ids: list[int]) -> None:
    """Local harness: park other portfolio loans so EOD jobs scan only the fixture group.

    Closes ACTIVE *and* FORECLOSURE_FREEZE (AssetCriteria reader includes both —
    F3 SU-FLOW-NPA-CRITERIA-FLIP: ACTIVE-only quarantine left 95+ FREEZE rows and
    the job FAILED on portfolio 'Invalid amount' before tagging the fixture LAN).
    """
    keep = ",".join(str(i) for i in [parent_account_id, *child_account_ids])
    psql_multi(f"""
CREATE TABLE IF NOT EXISTS mfi_accounting._dcf_fresh_billing_quarantine_backup (
  account_id BIGINT PRIMARY KEY,
  loan_status VARCHAR(32) NOT NULL,
  backed_up_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
INSERT INTO mfi_accounting._dcf_fresh_billing_quarantine_backup (account_id, loan_status)
SELECT la.account_id, la.loan_status
FROM mfi_accounting.loan_account la
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE') AND la.is_deleted = false
  AND la.account_id NOT IN ({keep})
  AND NOT EXISTS (
    SELECT 1 FROM mfi_accounting._dcf_fresh_billing_quarantine_backup b
    WHERE b.account_id = la.account_id
  );
UPDATE mfi_accounting.loan_account la
SET loan_status = 'CLOSED', updated_on = NOW(), updated_by = 'DCF_FRESH_BILLING_Q'
WHERE la.loan_status IN ('ACTIVE','FORECLOSURE_FREEZE') AND la.is_deleted = false
  AND la.account_id NOT IN ({keep});
""")


def restore_billing_portfolio_quarantine() -> None:
    psql_multi("""
UPDATE mfi_accounting.loan_account la
SET loan_status = b.loan_status, updated_on = NOW(), updated_by = 'DCF_FRESH_BILLING_Q_RESTORE'
FROM mfi_accounting._dcf_fresh_billing_quarantine_backup b
WHERE la.account_id = b.account_id;
DELETE FROM mfi_accounting._dcf_fresh_billing_quarantine_backup;
""")


def child_labd_count(account_id: int) -> int:
    row = psql(f"""
SELECT COUNT(*)::text FROM mfi_accounting.loan_account_billing_details
WHERE account_id = {account_id};
""")
    return int(row or "0")
