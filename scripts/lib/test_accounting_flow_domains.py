#!/usr/bin/env python3
"""Tests for accounting flow domain resolver."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from accounting_flow_domains import detect_domains, touches_accounting  # noqa: E402
from resolve_ship_cases import resolve_ship_cases  # noqa: E402


def _reg() -> dict:
    return json.loads((ROOT / "scripts/testing/registry.json").read_text(encoding="utf-8"))


class AccountingDomainsTest(unittest.TestCase):
    def test_read_processor_maps_read_inquiry(self) -> None:
        blob = "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/processor/getloanaccountoverviewdetailsprocessor.java"
        self.assertIn("read_inquiry", detect_domains(blob, set()))

    def test_interest_batch_maps_domain(self) -> None:
        blob = "batchnew/interest/interestaccrualbooking/interestaccrualbookingbatchservice.java"
        self.assertIn("interest_accrual", detect_domains(blob, set()))

    def test_service_tier_adds_read_smoke(self) -> None:
        paths = [
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/processor/GetLoanAccountSummaryDetailsProcessor.java"
        ]
        out = resolve_ship_cases(paths, ["getLoanAccountSummaryDetails"], "service", _reg())
        self.assertTrue(
            "accounting.read_smoke" in out or "health.accounting" in out or "dpic.summary_api" in out
        )

    def test_touches_accounting_from_repo_path(self) -> None:
        self.assertTrue(
            touches_accounting(
                "trustt-platform-accounting/src/foo.java",
                set(),
                ["trustt-platform-accounting"],
            )
        )


if __name__ == "__main__":
    unittest.main()
