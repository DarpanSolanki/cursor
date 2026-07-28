#!/usr/bin/env python3
"""Permanent ship-test autonomy: change → api → ntest cases (no invent / no freeze)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from accounting_flow_domains import detect_domains, path_blob  # noqa: E402
from change_test_map import api_from_class_stem  # noqa: E402
from infer_ship_apis import build_impact  # noqa: E402
from kg_ship_resolve import resolve_apis_for_path  # noqa: E402
from register_pending_ship import register_paths  # noqa: E402
from resolve_ship_impact import resolve  # noqa: E402
from ship_push_gate import ship_loop_satisfied  # noqa: E402
from ship_fingerprint import repo_head_sha  # noqa: E402


class ChangeTestMapTest(unittest.TestCase):
    def test_penal_batch_stem_maps_correctly(self) -> None:
        self.assertEqual(
            api_from_class_stem("PenalInterestAccrualCalculationBatchService"),
            "penalInterestAccrualCalculation",
        )

    def test_due_writer_maps_to_job(self) -> None:
        self.assertEqual(
            api_from_class_stem("LoanInstallmentDueNotificationWriter"),
            "loanInstallmentDueNotificationJob",
        )

    def test_booking_maps_to_posting_api(self) -> None:
        self.assertEqual(
            api_from_class_stem("InterestAccrualBookingBatchService"),
            "interestAccrualPosting",
        )


class DomainDetectTest(unittest.TestCase):
    def test_penal_does_not_hit_interest_accrual(self) -> None:
        blob = path_blob(
            [
                "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
                "penal/penalinterestaccrualcalculation/PenalInterestAccrualCalculationBatchService.java"
            ]
        )
        domains = detect_domains(blob)
        self.assertIn("penal_interest", domains)
        self.assertNotIn("interest_accrual", domains)

    def test_advance_domain_not_repayment_dpi(self) -> None:
        blob = path_blob(
            [
                "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
                "loanadvancerepayment/LoanAdvanceRepaymentBatchService.java"
            ]
        )
        domains = detect_domains(blob)
        self.assertIn("loan_advance_repayment", domains)
        self.assertNotIn("repayment", domains)


class ResolveImpactTest(unittest.TestCase):
    def test_penal_impact_cases(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
            "penal/penalinterestaccrualcalculation/PenalInterestAccrualCalculationBatchService.java"
        )
        apis = resolve_apis_for_path(path)
        self.assertIn("penalInterestAccrualCalculation", apis)
        impact = build_impact([path])
        # penal scope=out — must not auto-select batch penal cases
        self.assertNotIn("batch.penal_interest_accrual_calc", impact["ntest_cases"])
        self.assertNotIn("batch.interest_accrual_calc", impact["ntest_cases"])

    def test_advance_impact_not_dpi_repayment(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
            "loanadvancerepayment/LoanAdvanceRepaymentBatchService.java"
        )
        impact = build_impact([path])
        self.assertIn("loanAdvanceRepayment", impact["apis"])
        self.assertIn("batch.loan_advance_repayment", impact["ntest_cases"])
        self.assertNotIn("dpic.repayment_e2e", impact["ntest_cases"])

    def test_derivedfields_does_not_invent_disburse(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
            "derivedfields/SomeDerivedFieldsService.java"
        )
        apis = resolve_apis_for_path(path)
        self.assertNotIn("disburseLoan", apis)
        impact = build_impact([path])
        self.assertNotIn("disbursement.quick", impact.get("ntest_cases") or [])

    def test_resolve_ship_impact_reresolves_frozen_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Minimal stubs: point resolve at real ROOT libs but fake pending under td
            pending = root / ".cursor" / ".pending-ship-work.json"
            pending.parent.mkdir(parents=True)
            rel = (
                "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
                "penal/penalinterestaccrualcalculation/PenalInterestAccrualCalculationBatchService.java"
            )
            # Create empty file so fingerprints work when needed
            (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
            pending.write_text(
                json.dumps(
                    {
                        "tier": "money",
                        "files": [rel],
                        "apis": ["disburseLoan"],
                        "registry_cases": ["disbursement.quick"],
                        "repos": ["trustt-platform-accounting"],
                        "updated_at": "2020-01-01T00:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            out = resolve(ROOT, pending, "", [], True)
            self.assertNotIn("disburseLoan", out["apis"])
            self.assertNotIn("disbursement.quick", out["ntest_cases"])
            self.assertNotIn("batch.penal_interest_accrual_calc", out["ntest_cases"])
            refreshed = json.loads(pending.read_text(encoding="utf-8"))
            self.assertNotIn("batch.penal_interest_accrual_calc", refreshed.get("registry_cases") or [])


    def test_resolve_uses_impact_tests_selection(self) -> None:
        from impact_tests import build_plan  # noqa: WPS433

        if not (ROOT / ".cursor/.pending-ship-work.json").is_file():
            self.skipTest("no pending ship work")
        plan = build_plan(from_pending=True, shipped_only=True)
        out = resolve(ROOT, ROOT / ".cursor/.pending-ship-work.json", "", [], True)
        self.assertEqual(
            sorted(out.get("ntest_cases") or []),
            sorted(plan.get("ordered_cases") or []),
        )
        self.assertEqual(out.get("selection_source"), "impact_tests")

    def test_head_sha_mismatch_unsatisfies(self) -> None:
        acc = ROOT / "trustt-platform-accounting"
        if not (acc / ".git").is_dir():
            self.skipTest("accounting repo missing")
        head = repo_head_sha(acc)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            pending = {
                "tier": "service",
                "files": ["trustt-platform-accounting/src/main/java/x.java"],
                "apis": [],
                "repos": ["trustt-platform-accounting"],
                "updated_at": "2020-01-01T00:00:00Z",
            }
            passed = {
                "passed_at": "2020-01-02T00:00:00Z",
                "tier": "service",
                "apis": [],
                "repo_head_shas": {"trustt-platform-accounting": head},
            }
            pp = cursor / ".pending-ship-work.json"
            pas = cursor / ".ship-loop-passed.json"
            pp.write_text(json.dumps(pending), encoding="utf-8")
            pas.write_text(json.dumps(passed), encoding="utf-8")
            with mock.patch("ship_push_gate.repo_head_shas", return_value={"trustt-platform-accounting": head}):
                self.assertTrue(ship_loop_satisfied(pp, pas))
            passed["repo_head_shas"]["trustt-platform-accounting"] = "deadbeef" * 5
            pas.write_text(json.dumps(passed), encoding="utf-8")
            with mock.patch(
                "ship_push_gate.repo_head_shas",
                return_value={"trustt-platform-accounting": head},
            ):
                self.assertFalse(ship_loop_satisfied(pp, pas))


class RegisterPendingUsesSmartCases(unittest.TestCase):
    def test_register_paths_sets_ntest_cases(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            # register against real ROOT so build_impact finds registry
            pending = ROOT / ".cursor" / ".pending-ship-work.test-autonomy.json"
            try:
                rel = (
                    "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/"
                    "notifications/loaninstallmentduenotificationjob/LoanInstallmentDueNotificationWriter.java"
                )
                out = register_paths(
                    ROOT, [rel], pending_path=pending, source="test"
                )
                self.assertTrue(out.get("registered"))
                data = json.loads(pending.read_text(encoding="utf-8"))
                self.assertIn(
                    "batch.loan_installment_due_notification",
                    data.get("registry_cases") or [],
                )
                self.assertNotIn("disbursement.quick", data.get("registry_cases") or [])
            finally:
                pending.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
