#!/usr/bin/env python3
"""Tests for the reuse-query machine gate (fail-closed repo/DAO query change)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import reuse_query_gate as g  # noqa: E402

_REPO_FILE = (
    "trustt-platform-accounting/src/main/java/in/novopay/accounting/"
    "loan/billing/dao/LoanAccountBillingDetailsRepository.java"
)
_DAO_FILE = (
    "trustt-platform-accounting/src/main/java/in/novopay/accounting/"
    "loan/billing/dao/LoanAccountBillingDetailsDaoService.java"
)

_ORDER_BY_DIFF = """diff --git a/x b/x
@@ -13,4 +13,5 @@
-\tLoanAccountBillingDetailsEntity findByLoanInstallmentDetailsId(Long id);
+\t@Query(nativeQuery = true, value = "SELECT * FROM loan_account_billing_details WHERE loan_installment_details_id = ?1 "
+\t\t\t+ "ORDER BY id DESC LIMIT 1")
+\tLoanAccountBillingDetailsEntity findByLoanInstallmentDetailsId(Long id);
"""

_NON_QUERY_DIFF = """diff --git a/x b/x
@@ -1,3 +1,3 @@
-// old comment
+// new comment refactor
"""


class FileMatchTest(unittest.TestCase):
    def test_matches_repo_and_dao(self) -> None:
        self.assertTrue(g.is_repo_or_dao_file(_REPO_FILE))
        self.assertTrue(g.is_repo_or_dao_file(_DAO_FILE))
        self.assertTrue(g.is_repo_or_dao_file("a/FooDAOService.java"))

    def test_rejects_others(self) -> None:
        self.assertFalse(g.is_repo_or_dao_file("a/FooProcessor.java"))
        self.assertFalse(g.is_repo_or_dao_file("a/FooEntity.java"))
        self.assertFalse(g.is_repo_or_dao_file("a/Repository.md"))


class SignalTest(unittest.TestCase):
    def test_detects_order_by_limit_query(self) -> None:
        sig = g.diff_query_signals(_ORDER_BY_DIFF)
        self.assertIn("ORDER BY", sig)
        self.assertIn("LIMIT", sig)
        self.assertIn("@Query", sig)

    def test_detects_finder_signature(self) -> None:
        diff = "@@\n+\tList<FooEntity> findAllByAccountId(Long accountId);\n"
        self.assertIn("finder-signature", g.diff_query_signals(diff))

    def test_ignores_where_in_unchanged_context(self) -> None:
        diff = "@@\n \tString sql = \"WHERE x = 1\";\n"  # context line (leading space)
        self.assertEqual([], g.diff_query_signals(diff))

    def test_non_query_diff_empty(self) -> None:
        self.assertEqual([], g.diff_query_signals(_NON_QUERY_DIFF))

    def test_empty_diff(self) -> None:
        self.assertEqual([], g.diff_query_signals(""))


class BlockValidationTest(unittest.TestCase):
    def _valid(self) -> dict:
        return {
            "reuse_queries_step": 2,
            "existing_methods_checked": ["findByLoanInstallmentDetailsId", "findOneByAccountId"],
            "callers_checked": ["DeathForeclosureInsuranceWriter", "LoanAccountBillingBatchService"],
            "performance_impact": "indexed on loan_installment_details_id; LIMIT 1 keeps it cheap",
        }

    def test_valid_step2(self) -> None:
        self.assertEqual([], g.reuse_query_block_errors(self._valid()))

    def test_missing_block(self) -> None:
        self.assertTrue(g.reuse_query_block_errors(None))

    def test_empty_lists_fail(self) -> None:
        b = self._valid()
        b["existing_methods_checked"] = []
        self.assertTrue(any("existing_methods_checked" in e for e in g.reuse_query_block_errors(b)))

    def test_step3_needs_justification(self) -> None:
        b = self._valid()
        b["reuse_queries_step"] = 3
        errs = g.reuse_query_block_errors(b)
        self.assertTrue(any("new_query_justification" in e for e in errs))

    def test_step3_with_justification_ok(self) -> None:
        b = self._valid()
        b["reuse_queries_step"] = 3
        b["new_query_justification"] = "no list finder exists; extending hot query would regress batch"
        self.assertEqual([], g.reuse_query_block_errors(b))

    def test_bad_step(self) -> None:
        b = self._valid()
        b["reuse_queries_step"] = 5
        self.assertTrue(any("reuse_queries_step" in e for e in g.reuse_query_block_errors(b)))


class ScanAndCheckTest(unittest.TestCase):
    def _getter(self, mapping: dict[str, str]):
        def _g(repo: str, rel: str) -> str:
            return mapping.get(f"{repo}/{rel}", "")

        return _g

    def test_scan_triggers_on_repo_query_change(self) -> None:
        repo, rel = _REPO_FILE.split("/", 1)
        triggered = g.scan_files(
            [_REPO_FILE, "trustt-platform-accounting/src/Foo.java"],
            diff_getter=self._getter({f"{repo}/{rel}": _ORDER_BY_DIFF}),
        )
        self.assertEqual(1, len(triggered))
        self.assertEqual(_REPO_FILE, triggered[0]["file"])

    def test_scan_ignores_non_query_repo_diff(self) -> None:
        repo, rel = _REPO_FILE.split("/", 1)
        triggered = g.scan_files(
            [_REPO_FILE], diff_getter=self._getter({f"{repo}/{rel}": _NON_QUERY_DIFF})
        )
        self.assertEqual([], triggered)

    def test_check_fails_without_block(self) -> None:
        repo, rel = _REPO_FILE.split("/", 1)
        errs = g.check(
            {"files": [_REPO_FILE]},
            {},
            diff_getter=self._getter({f"{repo}/{rel}": _ORDER_BY_DIFF}),
        )
        self.assertTrue(errs)

    def test_check_passes_with_valid_block(self) -> None:
        repo, rel = _REPO_FILE.split("/", 1)
        disc = {
            "reuse_query": {
                "reuse_queries_step": 2,
                "existing_methods_checked": ["findByLoanInstallmentDetailsId"],
                "callers_checked": ["DeathForeclosureInsuranceWriter"],
                "performance_impact": "LIMIT 1 on indexed column",
            }
        }
        errs = g.check(
            {"files": [_REPO_FILE]},
            disc,
            diff_getter=self._getter({f"{repo}/{rel}": _ORDER_BY_DIFF}),
        )
        self.assertEqual([], errs)

    def test_check_noop_when_not_triggered(self) -> None:
        errs = g.check(
            {"files": ["trustt-platform-accounting/src/Foo.java"]},
            {},
            diff_getter=self._getter({}),
        )
        self.assertEqual([], errs)


if __name__ == "__main__":
    unittest.main()
