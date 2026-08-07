#!/usr/bin/env python3
"""reverseTransaction — per-transaction double-entry and per-leg mirror proof.

Runs both ledger primitives for real against the local accounting service:
postTransaction writes an original pair of legs, reverseTransaction writes the
mirror. Every assert is scoped to the transaction_master rows this run created,
via the run's own stan, so a concurrent money flow on the same database cannot
make it pass or fail.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

from lib.api_client import fire_api, fresh_stan  # noqa: E402
from lib.envelope import build_envelope  # noqa: E402

LAN = os.environ.get("LEDGER_PRIMITIVE_LAN", "0000002972")
OFFICE_ID = os.environ.get("LEDGER_PRIMITIVE_OFFICE_ID", "2")
AMOUNT = os.environ.get("LEDGER_PRIMITIVE_AMOUNT", "37.00")

ASSERT_SQL = """
WITH orig AS (
  SELECT id, original_amount, reference_number, reversed, reversal_reference_number
  FROM mfi_accounting.transaction_master WHERE stan = '{post_stan}' AND reversal = false
), rev AS (
  SELECT id, original_amount, reference_number, client_reference_number, reversal
  FROM mfi_accounting.transaction_master WHERE stan = '{rev_stan}' AND reversal = true
), od AS (
  SELECT d.account_number,
         SUM(CASE WHEN d.cr_dr_indicator = 'D' THEN d.net_amount ELSE -d.net_amount END) AS net
  FROM mfi_accounting.transaction_details d JOIN orig ON orig.id = d.transaction_id
  GROUP BY d.account_number
), rd AS (
  SELECT d.account_number,
         SUM(CASE WHEN d.cr_dr_indicator = 'D' THEN d.net_amount ELSE -d.net_amount END) AS net
  FROM mfi_accounting.transaction_details d JOIN rev ON rev.id = d.transaction_id
  GROUP BY d.account_number
), op AS (
  SELECT p.account_number, p.reference_code,
         SUM(CASE WHEN p.cr_dr_indicator = 'D' THEN p.amount ELSE -p.amount END) AS net
  FROM mfi_accounting.transaction_partition_details p JOIN orig ON orig.id = p.transaction_id
  GROUP BY p.account_number, p.reference_code
), rp AS (
  SELECT p.account_number, p.reference_code,
         SUM(CASE WHEN p.cr_dr_indicator = 'D' THEN p.amount ELSE -p.amount END) AS net
  FROM mfi_accounting.transaction_partition_details p JOIN rev ON rev.id = p.transaction_id
  GROUP BY p.account_number, p.reference_code
), mirror AS (
  SELECT COALESCE(od.account_number, rd.account_number) AS acct,
         COALESCE(od.net, 0) + COALESCE(rd.net, 0) AS residual
  FROM od FULL OUTER JOIN rd ON rd.account_number = od.account_number
), mirror_p AS (
  SELECT COALESCE(op.account_number, rp.account_number) AS acct,
         COALESCE(op.reference_code, rp.reference_code) AS ref,
         COALESCE(op.net, 0) + COALESCE(rp.net, 0) AS residual
  FROM op FULL OUTER JOIN rp ON rp.account_number = op.account_number
                            AND rp.reference_code = op.reference_code
), tot AS (
  SELECT (SELECT COALESCE(SUM(net), 0) FROM rd) AS rev_net,
         (SELECT COALESCE(SUM(net), 0) FROM rp) AS rev_p_net,
         (SELECT count(*) FROM mfi_accounting.transaction_details d
            JOIN rev ON rev.id = d.transaction_id) AS rev_legs,
         (SELECT count(*) FROM mfi_accounting.transaction_details d
            JOIN orig ON orig.id = d.transaction_id) AS orig_legs
)
SELECT CASE
  WHEN (SELECT count(*) FROM orig) <> 1 THEN 'NO_ORIGINAL:' || (SELECT count(*) FROM orig)::text
  WHEN (SELECT count(*) FROM rev) <> 1 THEN 'NO_REVERSAL:' || (SELECT count(*) FROM rev)::text
  WHEN (SELECT reversed FROM orig) IS NOT TRUE THEN 'ORIGINAL_NOT_FLAGGED_REVERSED'
  WHEN (SELECT reversal_reference_number FROM orig) IS DISTINCT FROM (SELECT reference_number FROM rev)
    THEN 'REVERSAL_LINK_BROKEN:' || COALESCE((SELECT reversal_reference_number FROM orig), 'NULL')
  WHEN (SELECT client_reference_number FROM rev) <> 'R_{crn}'
    THEN 'REVERSAL_CRN:' || (SELECT client_reference_number FROM rev)
  WHEN (SELECT rev_legs FROM tot) <> (SELECT orig_legs FROM tot)
    THEN 'LEG_COUNT:' || (SELECT rev_legs FROM tot)::text || 'vs' || (SELECT orig_legs FROM tot)::text
  WHEN (SELECT rev_net FROM tot) <> 0 THEN 'REV_UNBALANCED:' || (SELECT rev_net::text FROM tot)
  WHEN (SELECT rev_p_net FROM tot) <> 0 THEN 'REV_TPD_UNBALANCED:' || (SELECT rev_p_net::text FROM tot)
  WHEN EXISTS (SELECT 1 FROM mirror WHERE residual <> 0)
    THEN 'LEG_NOT_MIRRORED:' || (SELECT acct || '=' || residual::text FROM mirror
                                 WHERE residual <> 0 ORDER BY acct LIMIT 1)
  WHEN EXISTS (SELECT 1 FROM mirror_p WHERE residual <> 0)
    THEN 'TPD_NOT_MIRRORED:' || (SELECT acct || '/' || ref || '=' || residual::text FROM mirror_p
                                 WHERE residual <> 0 ORDER BY acct, ref LIMIT 1)
  WHEN (SELECT original_amount FROM rev) <> (SELECT original_amount FROM orig)
    THEN 'REV_AMOUNT:' || (SELECT original_amount::text FROM rev)
  ELSE 'SUCCESS' END
"""


def db_scalar(sql: str) -> str:
    return subprocess.check_output(
        ["psql",
         "-h", os.environ.get("YB_HOST", "127.0.0.1"),
         "-p", os.environ.get("YB_PORT", "5433"),
         "-U", os.environ.get("YB_USER", "yugabyte"),
         "-d", os.environ.get("YB_DB", "yugabyte"),
         "-t", "-A", "-v", "ON_ERROR_STOP=1", "-c", sql],
        env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
        text=True, timeout=120).strip()


def main() -> int:
    post_stan = fresh_stan("revtxn_post")
    crn = "RT_" + post_stan
    post_req = {
        "basic_details": {
            "office_id": OFFICE_ID,
            "originating_office_id": OFFICE_ID,
            "transaction_type": "INTEREST",
            "transaction_sub_type": "NORMAL_ACCRUAL",
            "client_reference_number": crn,
            "currency": "INR",
            "amount": AMOUNT,
            "value_date": str(int(time.time() * 1000)),
            "remarks": "reverseTransaction double-entry probe",
        },
        "account_details": [
            {"placeholder": "LOAN_ACCOUNT", "account_number": LAN, "narration": "reversal probe"}
        ],
    }
    post = fire_api(
        "postTransaction",
        build_envelope("accounting", post_req, stan=post_stan,
                       header_overrides={"operation_mode": "SELF"}),
        service="accounting")
    code, status = post.response_status()
    print(f"postTransaction HTTP {post.http_status} {code}/{status} crn={crn}")
    if status.upper() != "SUCCESS":
        print(post.body[:800])
        print("RESULT: FAIL — postTransaction did not post the original")
        return 1

    rev_stan = fresh_stan("revtxn_rev")
    rev = fire_api(
        "reverseTransaction",
        build_envelope("accounting", {"client_reference_number": crn}, stan=rev_stan,
                       header_overrides={"operation_mode": "SELF"}),
        service="accounting")
    code, status = rev.response_status()
    print(f"reverseTransaction HTTP {rev.http_status} {code}/{status}")
    if status.upper() != "SUCCESS":
        print(rev.body[:800])
        print("RESULT: FAIL — reverseTransaction did not post the mirror")
        return 1

    sql = ASSERT_SQL.format(post_stan=post_stan, rev_stan=rev_stan, crn=crn)
    if os.environ.get("REVTXN_PERTURB_SQL"):
        subprocess.check_call(
            ["bash", str(ROOT / "scripts" / "bin" / "db-local-write.sh"),
             "--file", os.environ["REVTXN_PERTURB_SQL"]],
            env={**os.environ, "REVTXN_POST_STAN": post_stan, "REVTXN_REV_STAN": rev_stan})
    verdict = db_scalar(sql)
    print(f"double_entry_mirror: {verdict}")
    print(f"LAYERS_DECLARE: jobs=REAL(postTransaction,reverseTransaction) lan={LAN} "
          f"post_stan={post_stan} rev_stan={rev_stan}")
    if verdict != "SUCCESS":
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
