#!/usr/bin/env python3
"""Permanent ship-test autonomy: change → api → ntest cases (no invent / no freeze)."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from accounting_flow_domains import detect_domains, path_blob  # noqa: E402
from change_test_map import api_from_class_stem  # noqa: E402
from infer_ship_apis import build_impact  # noqa: E402
from kg_ship_resolve import resolve_apis_for_path  # noqa: E402
from register_pending_ship import register_paths  # noqa: E402
from resolve_ship_impact import resolve  # noqa: E402
from ship_push_gate import (  # noqa: E402
    fingerprints_for_files,
    ship_loop_satisfied,
)


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


class FingerprintGateTest(unittest.TestCase):
    def test_fingerprint_mismatch_unsatisfies(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            f = root / "scripts" / "lib" / "dummy_ship_fp.txt"
            f.parent.mkdir(parents=True)
            f.write_text("v1\n", encoding="utf-8")
            rel = "scripts/lib/dummy_ship_fp.txt"
            fps = fingerprints_for_files(root, [rel])
            pending = {
                "tier": "workspace",
                "files": [rel],
                "apis": [],
                "updated_at": "2020-01-01T00:00:00Z",
                "file_fingerprints": fps,
            }
            passed = {
                "passed_at": "2020-01-02T00:00:00Z",
                "tier": "workspace",
                "apis": [],
                "file_fingerprints": fps,
            }
            pp = cursor / ".pending-ship-work.json"
            pas = cursor / ".ship-loop-passed.json"
            pp.write_text(json.dumps(pending), encoding="utf-8")
            pas.write_text(json.dumps(passed), encoding="utf-8")
            self.assertTrue(ship_loop_satisfied(pp, pas))
            f.write_text("v2-changed\n", encoding="utf-8")
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
