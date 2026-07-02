#!/usr/bin/env python3
"""Unit tests for DPI ship-case resolution (consolidated ship-close verify)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from resolve_ship_cases import resolve_dpi_cases, resolve_ship_cases  # noqa: E402


def _load_reg() -> dict:
    return json.loads((ROOT / "scripts/testing/registry.json").read_text(encoding="utf-8"))


class ResolveDpiCasesTest(unittest.TestCase):
    def test_booking_path_uses_consolidated_ship_close(self) -> None:
        blob = "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/dpiaccrualbookingbatchservice.java"
        apis = {"dpiAccrualBooking"}
        out = resolve_dpi_cases(blob, apis, [])
        self.assertIn("batch.dpi_booking", out)
        self.assertIn("dpic.ship_close_verify", out)
        self.assertNotIn("dpic.posting_calendar_regression", out)
        self.assertNotIn("dpic.cross_eod_replay_134497", out)

    def test_billing_path_uses_consolidated_ship_close(self) -> None:
        blob = "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/dpi/dpibilling/dpibillingbatchservice.java"
        apis = {"dpiBilling"}
        out = resolve_dpi_cases(blob, apis, [])
        self.assertIn("batch.dpi_billing", out)
        self.assertIn("dpic.ship_close_verify", out)
        self.assertNotIn("dpic.billing_ud_next_emi", out)

    def test_money_tier_booking_ship_auto_includes_ship_close(self) -> None:
        reg = _load_reg()
        paths = [
            "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/DpiAccrualBookingBatchService.java"
        ]
        apis = ["dpiAccrualBooking"]
        out = resolve_ship_cases(paths, apis, "money", reg)
        self.assertIn("dpic.ship_close_verify", out)
        self.assertNotIn("dpic.posting_calendar_regression", out)

    def test_npa_fixture_sql_does_not_pull_npa_movement_e2e(self) -> None:
        reg = _load_reg()
        paths = [
            "scripts/dpic/sql/helpers/setup_qa1_month_end_npa_fixture.sql",
            "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/batchnew/dpi/dpiaccrualbooking/DpiAccrualBookingBatchService.java",
        ]
        apis = ["dpiAccrualBooking"]
        out = resolve_ship_cases(paths, apis, "money", reg)
        self.assertIn("dpic.ship_close_verify", out)
        self.assertNotIn("dpic.npa_dpi_movement_e2e", out)

    def test_read_overview_ship_does_not_pull_unrelated_dpi_e2e(self) -> None:
        reg = _load_reg()
        paths = [
            "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/processor/GetLoanAccountOverviewDetailsProcessor.java",
            "novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/recurring/batch/LoanRecurringPaymentBatchProcessor.java",
        ]
        apis = ["getLoanAccountOverviewDetails", "loanRecurringPaymentBatchApi"]
        out = resolve_ship_cases(paths, apis, "money", reg)
        self.assertIn("dpic.overview_api", out)
        self.assertNotIn("foreclosure.individual_child", out)
        self.assertNotIn("dpic.repayment_e2e", out)
        self.assertNotIn("dpic.part_prepayment_write_e2e", out)
        self.assertNotIn("dpic.cross_eod_replay_134497", out)


if __name__ == "__main__":
    unittest.main()
