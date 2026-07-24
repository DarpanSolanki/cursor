"""Generic fixture snapshot / restore — table-set is a FixtureProfile parameter."""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from .db import PG, PG_ENV, SCH, psql as q1_retry
from .lock import acquire_flowtest_lock
from .profiles import DCF_GROUP, FixtureProfile, PROFILES

# q1 without retry loop for schema checks (fast fail)
def q1(sql: str) -> str:
    out = subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
    return out.strip().split("\n")[0] if out.strip() else ""


def run(sql: str, *, retries: int = 1) -> None:
    last_err: subprocess.CalledProcessError | None = None
    for attempt in range(1, retries + 1):
        try:
            subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)
            return
        except subprocess.CalledProcessError as exc:
            last_err = exc
            if attempt >= retries:
                raise
            time.sleep(min(2 * attempt, 8))
    if last_err:
        raise last_err


def bak_schema(parent_lan: str, profile: FixtureProfile) -> str:
    return f"{profile.schema_prefix}_{parent_lan}"


def resolve_fixture(parent_lan: str) -> tuple[str, list[str], list[str]]:
    parent_id = q1(f"SELECT account_id FROM {SCH}.loan_account WHERE la_account_number='{parent_lan}';")
    if not parent_id:
        raise SystemExit(f"parent LAN not found: {parent_lan}")
    rows = subprocess.check_output(
        [
            *PG,
            "-c",
            f"SELECT account_id, la_account_number FROM {SCH}.loan_account "
            f"WHERE account_id={parent_id} OR parent_loan_account_id={parent_id} ORDER BY account_id;",
        ],
        env=PG_ENV,
        text=True,
    ).strip().split("\n")
    ids, lans = [], []
    for r in rows:
        if not r.strip():
            continue
        aid, lan = r.split("|", 1)
        ids.append(aid.strip())
        lans.append(lan.strip())
    return parent_id, ids, lans


def _numeric_billing_crn_clause(ids: list[str]) -> str:
    return " OR ".join(
        f"(tm.client_reference_number ~ '^{aid}[0-9]+$' AND EXISTS ("
        f"SELECT 1 FROM {SCH}.transaction_catalogue tc "
        f"WHERE tc.id = tm.transaction_catalogue_id AND tc.type = 'BILLING'))"
        for aid in ids
    )


def _test_txn_ids_subquery(
    lan_list: str, ids: list[str], bak: str, profile: FixtureProfile
) -> str:
    if profile.purge_numeric_billing_crn:
        crn = _numeric_billing_crn_clause(ids)
        return (
            f"(SELECT tm.id FROM {SCH}.transaction_master tm WHERE ("
            f"tm.id IN (SELECT DISTINCT td.transaction_id FROM {SCH}.transaction_details td "
            f"WHERE td.account_number IN ({lan_list})) OR {crn}) "
            f"AND tm.id NOT IN (SELECT id FROM {bak}.transaction_master_ids))"
        )
    return (
        f"(SELECT tm.id FROM {SCH}.transaction_master tm WHERE "
        f"tm.id IN (SELECT DISTINCT td.transaction_id FROM {SCH}.transaction_details td "
        f"WHERE td.account_number IN ({lan_list})) "
        f"AND tm.id NOT IN (SELECT id FROM {bak}.transaction_master_ids))"
    )


def snapshot(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> None:
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    lan_list = ",".join(f"'{x}'" for x in lans)
    bak = bak_schema(parent_lan, profile)
    print(f"snapshot profile={profile.name} parent={parent_lan} accounts={len(ids)} -> schema {bak}")

    stmts = [f"DROP SCHEMA IF EXISTS {bak} CASCADE;", f"CREATE SCHEMA {bak};"]
    stmts.append(
        f"CREATE TABLE {bak}.loan_account AS SELECT * FROM {SCH}.loan_account WHERE account_id IN ({id_list});"
    )
    stmts.append(
        f"CREATE TABLE {bak}.account AS SELECT * FROM {SCH}.account WHERE id IN ({id_list});"
    )
    for t in profile.scoped_by_loan_account_id:
        stmts.append(
            f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE loan_account_id IN ({id_list});"
        )
    for t in profile.scoped_by_account_id:
        stmts.append(
            f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE account_id IN ({id_list});"
        )
    for t in profile.scoped_by_account_number:
        stmts.append(
            f"CREATE TABLE {bak}.{t} AS SELECT * FROM {SCH}.{t} WHERE account_number IN ({lan_list});"
        )
    stmts.append(
        f"CREATE TABLE {bak}.transaction_master_ids AS "
        f"SELECT DISTINCT td.transaction_id AS id FROM {SCH}.transaction_details td "
        f"WHERE td.account_number IN ({lan_list});"
    )
    run("\n".join(stmts))
    print("  snapshot done")


def restore(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> None:
    acquire_flowtest_lock()
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    lan_list = ",".join(f"'{x}'" for x in lans)
    bak = bak_schema(parent_lan, profile)
    if q1(f"SELECT 1 FROM information_schema.schemata WHERE schema_name='{bak}';") != "1":
        raise SystemExit(f"no snapshot for {parent_lan} (schema {bak} missing) — run snapshot first")
    print(f"restore profile={profile.name} parent={parent_lan} accounts={len(ids)} from schema {bak}")

    stmts = ["SET session_replication_role = replica;"]
    test_txns = _test_txn_ids_subquery(lan_list, ids, bak, profile)
    stmts.append(f"DELETE FROM {SCH}.transaction_partition_details WHERE transaction_id IN {test_txns};")
    stmts.append(f"DELETE FROM {SCH}.transaction_details WHERE transaction_id IN {test_txns};")
    stmts.append(f"DELETE FROM {SCH}.transaction_master WHERE id IN {test_txns};")
    if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='account';") == "1":
        stmts.append(f"DELETE FROM {SCH}.account WHERE id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.account SELECT * FROM {bak}.account;")
    else:
        stmts.append(
            f"UPDATE {SCH}.account SET status='ACTIVE', updated_on=NOW(), updated_by='FLOWTEST_RESTORE_HEAL' "
            f"WHERE id IN ({id_list}) AND COALESCE(status,'') <> 'ACTIVE';"
        )
    stmts.append(f"DELETE FROM {SCH}.loan_account WHERE account_id IN ({id_list});")
    stmts.append(f"INSERT INTO {SCH}.loan_account SELECT * FROM {bak}.loan_account;")
    for t in profile.scoped_by_loan_account_id:
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='{t}';") != "1":
            # Older bak schemas (pre-F3) may lack newly profiled tables — skip, do not leak.
            print(f"  skip restore {t}: not in {bak} (re-snapshot to include)")
            continue
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE loan_account_id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    for t in profile.scoped_by_account_id:
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='{t}';") != "1":
            continue
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE account_id IN ({id_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    for t in profile.scoped_by_account_number:
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='{t}';") != "1":
            continue
        stmts.append(f"DELETE FROM {SCH}.{t} WHERE account_number IN ({lan_list});")
        stmts.append(f"INSERT INTO {SCH}.{t} SELECT * FROM {bak}.{t};")
    stmts.append("SET session_replication_role = origin;")
    run("\n".join(stmts), retries=6)
    print("  restore done")
    verify(parent_lan, profile)


def _fingerprint(scope_ids: str, from_schema: str | None) -> str:
    la = f"{from_schema}.loan_account" if from_schema else f"{SCH}.loan_account"
    ldd = f"{from_schema}.loan_due_details" if from_schema else f"{SCH}.loan_due_details"
    return q1(
        f"""
SELECT string_agg(x, '|' ORDER BY x) FROM (
  SELECT la.la_account_number||':'||la.loan_status||':'||
         COALESCE(SUM(d.paid_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0)||':'||
         COALESCE(SUM(d.waived_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0)||':'||
         COALESCE(SUM(d.due_amount-d.paid_amount-d.waived_amount) FILTER (WHERE d.component_type='PRIN' AND COALESCE(d.is_deleted,false)=false),0) AS x
  FROM {la} la LEFT JOIN {ldd} d ON d.loan_account_id=la.account_id
  WHERE la.account_id IN ({scope_ids})
  GROUP BY la.la_account_number, la.loan_status
) s;
"""
    )


def verify(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> None:
    parent_id, ids, lans = resolve_fixture(parent_lan)
    id_list = ",".join(ids)
    bak = bak_schema(parent_lan, profile)
    if q1(f"SELECT 1 FROM information_schema.schemata WHERE schema_name='{bak}';") != "1":
        raise SystemExit(f"no snapshot for {parent_lan}")
    live = _fingerprint(id_list, None)
    snap = _fingerprint(id_list, bak)
    if live == snap:
        print(f"  VERIFY OK — live matches snapshot ({len(ids)} loans)")
    else:
        print("  VERIFY MISMATCH")
        print(f"    snapshot: {snap}")
        print(f"    live    : {live}")
        raise SystemExit(1)


def drop(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> None:
    run(f"DROP SCHEMA IF EXISTS {bak_schema(parent_lan, profile)} CASCADE;")
    print(f"dropped {bak_schema(parent_lan, profile)}")


def has_snapshot(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> bool:
    bak = bak_schema(parent_lan, profile)
    return q1(f"SELECT 1 FROM information_schema.schemata WHERE schema_name='{bak}';") == "1"


def extend_bak_missing_tables(parent_lan: str, profile: FixtureProfile = DCF_GROUP) -> None:
    """Backfill newly profiled tables into an existing bak schema (F3 date-roll).

    Creates empty structural copies (LIKE … INCLUDING ALL) so restore can wipe
    live dirt without freezing pre-extend portfolio noise into the snapshot.
    """
    if not has_snapshot(parent_lan, profile):
        return
    bak = bak_schema(parent_lan, profile)
    stmts: list[str] = []
    for t in (
        *profile.scoped_by_loan_account_id,
        *profile.scoped_by_account_id,
        *profile.scoped_by_account_number,
    ):
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{bak}' AND table_name='{t}';") == "1":
            continue
        if q1(f"SELECT 1 FROM information_schema.tables WHERE table_schema='{SCH}' AND table_name='{t}';") != "1":
            continue
        stmts.append(f"CREATE TABLE {bak}.{t} (LIKE {SCH}.{t} INCLUDING ALL);")
        print(f"  extend bak: {bak}.{t} (empty LIKE — wipe-on-restore)")
    if stmts:
        run("\n".join(stmts))


def ensure_snapshot_or_restore(
    parent_lan: str, profile: FixtureProfile = DCF_GROUP, *, force_restore: bool = True
) -> None:
    """First run snapshots; later runs restore (default)."""
    if has_snapshot(parent_lan, profile):
        if force_restore:
            # Ensure new profile tables exist in bak before restore so DELETE/INSERT runs.
            extend_bak_missing_tables(parent_lan, profile)
            restore(parent_lan, profile)
            time.sleep(3)
    else:
        snapshot(parent_lan, profile)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) < 2 or argv[0] not in ("snapshot", "restore", "verify", "drop"):
        print(
            "Usage: python3 -m scripts.testing.flowtest.fixture "
            "<snapshot|restore|verify|drop> <parent_lan> [--profile NAME]\n"
            f"Profiles: {', '.join(PROFILES)}"
        )
        return 2
    op, parent = argv[0], argv[1]
    profile = DCF_GROUP
    if "--profile" in argv:
        i = argv.index("--profile")
        profile = PROFILES[argv[i + 1]]
    {"snapshot": snapshot, "restore": restore, "verify": verify, "drop": drop}[op](parent, profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
