#!/usr/bin/env python3
"""
DCF fixture snapshot / restore — retest the SAME group LANs repeatably.

The death-foreclosure e2e consumes its fixture (children + parent close). This tool takes a
full row-level backup of everything the DFC flow mutates for a group parent (parent + ALL its
children), and restores it exactly — so the same LANs can be re-run indefinitely.

No service code. Pure DB. Restore uses YugabyteDB `session_replication_role = replica` to bypass
FK checks during delete+reinsert, then resets to origin.

Usage:
  python3 scripts/dcf_sanity/dcf_fixture_backup.py snapshot <parent_lan>
  python3 scripts/dcf_sanity/dcf_fixture_backup.py restore  <parent_lan>
  python3 scripts/dcf_sanity/dcf_fixture_backup.py verify   <parent_lan>   # snapshot-vs-live diff
  python3 scripts/dcf_sanity/dcf_fixture_backup.py drop     <parent_lan>   # remove backup schema
"""
from __future__ import annotations

import atexit
import fcntl
import os
import subprocess
import sys
import time

PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql", "-h", os.environ.get("YB_HOST", "localhost"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-v", "ON_ERROR_STOP=1",
]
SCH = "mfi_accounting"
DCF_E2E_LOCK = "/tmp/dcf_e2e.lock"


def acquire_dcf_e2e_lock() -> int:
    if os.environ.get("DCF_E2E_LOCK_HELD") == "1":
        return -1
    lock_fd = os.open(DCF_E2E_LOCK, os.O_CREAT | os.O_RDWR, 0o664)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        os.close(lock_fd)
        raise SystemExit("DCF E2E already owns /tmp/dcf_e2e.lock; refusing fixture mutation") from exc
    atexit.register(os.close, lock_fd)
    return lock_fd

# Tables the DFC flow updates / inserts / soft-deletes, scoped to the fixture's loans.
SCOPED_BY_LOAN_ACCOUNT_ID = [
    "loan_due_details",
    "loan_installment_details",
    "loan_account_insurance_details",
    "loan_account_closure_details",
    "death_foreclosure_details",
    "waiver_details",
    "prepayment_details",
    "loan_account_part_prepayment_details",
]
# account_id-scoped (not loan_account_id) — required so restore undoes Obs1 labd dirt + account.status.
SCOPED_BY_ACCOUNT_ID = [
    "loan_account_billing_details",
    "interest_accrual_details",
]
SCOPED_BY_ACCOUNT_NUMBER = [
    "transaction_details",
    "transaction_partition_details",
    "death_foreclosure_insurance_staging_details",
]


def q1(sql: str) -> str:
    out = subprocess.check_output([*PG, "-tA", "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def run(sql: str, *, retries: int = 1) -> None:
    last_err: subprocess.CalledProcessError | None = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.check_call([*PG, "-c", sql], env=PG_ENV)
            return
        except subprocess.CalledProcessError as exc:
            last_err = exc
            if attempt >= retries:
                raise
            time.sleep(min(2 * attempt, 8))
    if last_err:
        raise last_err


def bak_schema(parent_lan: str) -> str:
    return f"dcf_bak_{parent_lan}"


def resolve_fixture(parent_lan: str) -> tuple[str, list[str], list[str]]:
    parent_id = q1(f"SELECT account_id FROM {SCH}.loan_account WHERE la_account_number='{parent_lan}';")
    if not parent_id:
        raise SystemExit(f"parent LAN not found: {parent_lan}")
    rows = subprocess.check_output(
        [*PG, "-tA", "-c",
         f"SELECT account_id, la_account_number FROM {SCH}.loan_account "
         f"WHERE account_id={parent_id} OR parent_loan_account_id={parent_id} ORDER BY account_id;"],
        env=PG_ENV, text=True,
    ).strip().split("\n")
    ids, lans = [], []
    for r in rows:
        aid, lan = r.split("|", 1)
        ids.append(aid.strip())
        lans.append(lan.strip())
    return parent_id, ids, lans


def _dfc_test_crn_clause(ids: list[str]) -> str:
    """Partial-cycle billing posts use GL account_number in transaction_details, not LAN — purge by CRN.

    Force-bill client_ref is platform-numeric: accountId||valueDateMs (all digits). Restrict to BILLING
    so we do not sweep unrelated numeric CRNs.
    """
    return " OR ".join(
        f"(tm.client_reference_number ~ '^{aid}[0-9]+$' AND EXISTS ("
        f"SELECT 1 FROM {SCH}.transaction_catalogue tc "
        f"WHERE tc.id = tm.transaction_catalogue_id AND tc.type = 'BILLING'))"
        for aid in ids
    )


def _test_txn_ids_subquery(id_list: str, lan_list: str, ids: list[str], bak: str) -> str:
    crn = _dfc_test_crn_clause(ids)
    return (
        f"(SELECT tm.id FROM {SCH}.transaction_master tm WHERE ("
        f"tm.id IN (SELECT DISTINCT td.transaction_id FROM {SCH}.transaction_details td "
        f"WHERE td.account_number IN ({lan_list})) OR {crn}) "
        f"AND tm.id NOT IN (SELECT id FROM {bak}.transaction_master_ids))"
    )


def snapshot(parent_lan: str) -> None:
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    lan_list = ",".join(f"'{x}'" for x in lans)
    bak = bak_schema(parent_lan)
    print(f"snapshot parent={parent_lan} accounts={len(ids)} -> schema {bak}")

    stmts = [f"DROP SCHEMA IF EXISTS {bak} CASCADE;", f"CREATE SCHEMA {bak};"]
    stmts.append(f"CREATE TABLE {bak}.loan_account AS SELECT * FROM {SCH}.loan_account WHERE account_id IN ({id_list});")
    # account row (status ACTIVE/CLOSED) — missing this left CLOSED after restore → Vikram AUTO 134468.
    stmts.append(f"CREATE TABLE {bak}.account AS SELECT * FROM {SCH}.account WHERE id IN ({id_list});")
    for t in SCOPED_BY_LOAN_ACCOUNT_ID:
        stmts.append(f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE loan_account_id IN ({id_list});")
    for t in SCOPED_BY_ACCOUNT_ID:
        stmts.append(f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE account_id IN ({id_list});")
    for t in SCOPED_BY_ACCOUNT_NUMBER:
        stmts.append(f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE account_number IN ({lan_list});")
    # original transaction_master ids for these LANs — restore deletes any NOT in this set.
    stmts.append(
        f"CREATE TABLE {bak}.transaction_master_ids AS "
        f"SELECT DISTINCT td.transaction_id AS id FROM {SCH}.transaction_details td "
        f"WHERE td.account_number IN ({lan_list});")
    run("\n".join(stmts))
    print("  snapshot done (loan_account+account+labd+iad+dues+txns)")


def restore(parent_lan: str) -> None:
    acquire_dcf_e2e_lock()
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    lan_list = ",".join(f"'{x}'" for x in lans)
    bak = bak_schema(parent_lan)
    if q1(f"SELECT 1 FROM information_schema.schemata WHERE schema_name='{bak}';") != "1":
        raise SystemExit(f"no snapshot for {parent_lan} (schema {bak} missing) — run snapshot first")
    print(f"restore parent={parent_lan} accounts={len(ids)} from schema {bak}")

    stmts = ["SET session_replication_role = replica;"]
    test_txns = _test_txn_ids_subquery(id_list, lan_list, ids, bak)
    # 1) drop test-created transactions (LAN-linked OR DFC partial-bill CRN); cascade details first
    stmts.append(f"DELETE FROM {SCH}.transaction_partition_details WHERE transaction_id IN {test_txns};")
    stmts.append(f"DELETE FROM {SCH}.transaction_details WHERE transaction_id IN {test_txns};")
    stmts.append(f"DELETE FROM {SCH}.transaction_master WHERE id IN {test_txns};")
    # 2) account + loan_account: exact row restore (account.status must return to ACTIVE)
    if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='account';") == "1":
        stmts.append(f"DELETE FROM {SCH}.account WHERE id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.account SELECT * FROM {bak}.account;")
    else:
        # Legacy snapshots without account table — heal CLOSED→ACTIVE so Vikram AUTO works.
        stmts.append(
            f"UPDATE {SCH}.account SET status='ACTIVE', updated_on=NOW(), updated_by='DCF_FIXTURE_RESTORE_HEAL' "
            f"WHERE id IN ({id_list}) AND COALESCE(status,'') <> 'ACTIVE';"
        )
    stmts.append(f"DELETE FROM {SCH}.loan_account WHERE account_id IN ({id_list});")
    stmts.append(f"INSERT INTO {SCH}.loan_account SELECT * FROM {bak}.loan_account;")
    # 3) loan-account-scoped tables
    for t in SCOPED_BY_LOAN_ACCOUNT_ID:
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE loan_account_id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    # 3b) account_id-scoped (labd / IAD) — skip if legacy snapshot lacks table
    for t in SCOPED_BY_ACCOUNT_ID:
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='{t}';") != "1":
            continue
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE account_id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    # 4) account-number-scoped tables
    for t in SCOPED_BY_ACCOUNT_NUMBER:
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE account_number IN ({lan_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    stmts.append("SET session_replication_role = origin;")
    run("\n".join(stmts), retries=6)
    print("  restore done")
    verify(parent_lan)


def _fingerprint(parent_lan: str, scope_ids: str, scope_lans: str, from_schema: str | None) -> str:
    """Financial fingerprint of the fixture: per-loan status + PRIN paid/waived/pending sums."""
    la = f"{from_schema}.loan_account" if from_schema else f"{SCH}.loan_account"
    ldd = f"{from_schema}.loan_due_details" if from_schema else f"{SCH}.loan_due_details"
    return q1(f"""
SELECT string_agg(x, '|' ORDER BY x) FROM (
  SELECT la.la_account_number||':'||la.loan_status||':'||
         COALESCE(SUM(d.paid_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0)||':'||
         COALESCE(SUM(d.waived_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0)||':'||
         COALESCE(SUM(d.due_amount-d.paid_amount-d.waived_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0) AS x
  FROM {la} la LEFT JOIN {ldd} d ON d.loan_account_id=la.account_id
  WHERE la.account_id IN ({scope_ids})
  GROUP BY la.la_account_number, la.loan_status
) s;
""")


def verify(parent_lan: str) -> None:
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    lan_list = ",".join(f"'{x}'" for x in lans)
    bak = bak_schema(parent_lan)
    if q1(f"SELECT 1 FROM information_schema.schemata WHERE schema_name='{bak}';") != "1":
        raise SystemExit(f"no snapshot for {parent_lan}")
    live = _fingerprint(parent_lan, id_list, lan_list, None)
    snap = _fingerprint(parent_lan, id_list, lan_list, bak)
    if live == snap:
        print(f"  VERIFY OK — live matches snapshot ({len(ids)} loans)")
    else:
        print("  VERIFY MISMATCH")
        print(f"    snapshot: {snap}")
        print(f"    live    : {live}")
        raise SystemExit(1)


def drop(parent_lan: str) -> None:
    run(f"DROP SCHEMA IF EXISTS {bak_schema(parent_lan)} CASCADE;")
    print(f"dropped {bak_schema(parent_lan)}")


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in ("snapshot", "restore", "verify", "drop"):
        print(__doc__)
        return 2
    {"snapshot": snapshot, "restore": restore, "verify": verify, "drop": drop}[sys.argv[1]](sys.argv[2])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
