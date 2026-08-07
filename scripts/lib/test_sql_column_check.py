#!/usr/bin/env python3
"""A guessed column must never reach psql, and a valid query must never be blocked.

The second half matters as much as the first: a checker with false positives gets
switched off, and then it protects nothing.

    python3 scripts/lib/test_sql_column_check.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import sql_column_check  # noqa: E402


class SqlColumnCheckTest(unittest.TestCase):

    def setUp(self) -> None:
        if not sql_column_check.load_tables():
            self.skipTest("schema oracle missing — run scripts/bin/schema-sync.sh")

    def test_typo_is_caught_with_the_real_table_named(self) -> None:
        problems = sql_column_check.check(
            "SELECT la.vrm_categry FROM mfi_accounting.loan_account la")
        self.assertEqual(len(problems), 1, problems)
        self.assertIn("mfi_accounting.loan_account", problems[0])
        self.assertIn("vrm_categry", problems[0])

    def test_append_only_table_has_no_soft_delete(self) -> None:
        problems = sql_column_check.check(
            "SELECT p.is_deleted FROM mfi_accounting.loan_account_payments_details p")
        self.assertTrue(problems)
        self.assertIn("is_deleted", problems[0])

    def test_valid_join_passes(self) -> None:
        self.assertEqual([], sql_column_check.check(
            "SELECT a.account_number, la.loan_status "
            "FROM mfi_accounting.loan_account la "
            "JOIN mfi_accounting.account a ON a.id = la.account_id "
            "WHERE la.parent_loan_account_id = 384460"))

    def test_cte_and_subquery_aliases_are_not_judged(self) -> None:
        self.assertEqual([], sql_column_check.check(
            "WITH p AS (SELECT id AS pid FROM mfi_accounting.loan_product) "
            "SELECT p.pid, x.anything FROM p JOIN (SELECT 1 AS anything) x ON true"))

    def test_unknown_table_is_left_alone(self) -> None:
        self.assertEqual([], sql_column_check.check(
            "SELECT t.whatever FROM some_schema.not_a_real_table t"))

    def test_bare_table_resolves_against_the_default_schema(self) -> None:
        problems = sql_column_check.check("SELECT la.nonexistent_col FROM loan_account la")
        self.assertTrue(problems)
        self.assertIn("mfi_accounting.loan_account", problems[0])

    def test_schema_qualified_prefix_is_not_read_as_a_column(self) -> None:
        self.assertEqual([], sql_column_check.check(
            "SELECT account_number FROM mfi_accounting.account"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
