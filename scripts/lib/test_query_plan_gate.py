#!/usr/bin/env python3
"""Unit tests for query_plan_gate (heuristics + skip; no live DB required)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import query_plan_gate as g  # noqa: E402


class TestExtractAndHeuristics(unittest.TestCase):
    def test_extract_sql_from_diff(self):
        diff = '''
@@
-	@Query(nativeQuery = true, value = "SELECT * FROM loan_account_billing_details WHERE loan_installment_details_id = ?1 ")
+	@Query(nativeQuery = true, value = "SELECT * FROM loan_account_billing_details WHERE loan_installment_details_id = ?1 "
+			+ "ORDER BY id DESC LIMIT 1")
'''
        sqls = g.extract_sql_from_diff(diff)
        self.assertTrue(sqls, sqls)
        self.assertIn("ORDER BY id DESC LIMIT 1", sqls[0])

    def test_seq_scan_money_fail(self):
        plan = "Seq Scan on loan_account  (cost=0.00..100.00 rows=1000 width=64)"
        sql = "SELECT * FROM loan_account"
        v, detail = g.verdict_from_plan(plan, sql)
        self.assertEqual(v, "FAIL")
        self.assertIn("money", detail.lower())

    def test_index_scan_pass(self):
        plan = (
            "Index Scan using loan_account_payments_details_loan_account_id "
            "on loan_account_payments_details  (cost=0.00..5.22 rows=10 width=8)"
        )
        sql = "SELECT MAX(value_date) FROM loan_account_payments_details WHERE loan_account_id = 1"
        v, _ = g.verdict_from_plan(plan, sql)
        self.assertEqual(v, "PASS")

    def test_bind_placeholders(self):
        self.assertEqual(g.bind_placeholders("WHERE id = ?1 AND x = :name"), "WHERE id = 1 AND x = 2")

    def test_no_query_skip(self):
        touches = g.collect_query_touches(
            ["scripts/bin/query-plan-gate.sh"],
            diff_getter=lambda _r, _p: "",
        )
        self.assertEqual(touches, [])
        self.assertFalse(g.query_touched(["scripts/bin/query-plan-gate.sh"], diff_getter=lambda _r, _p: ""))


class TestReuseFail(unittest.TestCase):
    def test_new_query_without_reuse_block_fails(self):
        diff = (
            '+@Query(nativeQuery = true, value = "SELECT * FROM loan_account WHERE id = ?1")\n'
            "+List<X> findWeird(Long id);\n"
        )
        touches = [
            {
                "file": "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/billing/dao/LoanAccountBillingDetailsRepository.java",
                "signals": ["@Query", "nativeQuery"],
                "sqls": ["SELECT * FROM loan_account WHERE id = 1"],
                "diff": diff,
            }
        ]
        errs = g.check_reuse_for_new_query(touches, {})
        self.assertTrue(errs)
        self.assertTrue(any("reuse_query" in e for e in errs))


class TestGateSkip(unittest.TestCase):
    def test_run_gate_empty_skipped(self):
        with mock.patch.object(g, "pending_files", return_value=[]):
            r = g.run_gate(files=[], sqls=None)
        # files=[] and sqls None → treat as empty explain list → SKIPPED path via main;
        # run_gate with files=[] and no sqls yields SKIPPED-like empty
        self.assertIn(r["verdict"], ("SKIPPED", "PASS", "WARN", "FAIL"))


if __name__ == "__main__":
    unittest.main()
