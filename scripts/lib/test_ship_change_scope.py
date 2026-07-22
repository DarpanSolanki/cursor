#!/usr/bin/env python3
"""Tests for change-scoped ship resolution (workspace-wide)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from ship_change_scope import (  # noqa: E402
    collapse_subsumed_cases,
    dpi_ship_modules,
    harness_cases_for_paths,
    partition_ship_paths,
    resolve_change_scope,
)


def _reg() -> dict:
    return json.loads((ROOT / "scripts/testing/registry.json").read_text(encoding="utf-8"))


class PartitionPathsTest(unittest.TestCase):
    def test_splits_service_harness_kb(self) -> None:
        paths = [
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi/dpibilling/DpiBillingBatchService.java",
            "scripts/dpic/sql/helpers/verify_dpi_full_pipeline.sql",
            "scripts/testing/registry.json",
            ".cursor/changelog.md",
        ]
        p = partition_ship_paths(paths)
        self.assertEqual(1, len(p["service"]))
        self.assertEqual(1, len(p["harness"]))
        self.assertEqual(1, len(p["testing_infra"]))
        self.assertEqual(1, len(p["workspace_kb"]))


class HarnessOnlyTest(unittest.TestCase):
    def test_harness_sql_does_not_pull_full_dpi_suite(self) -> None:
        paths = ["scripts/dpic/sql/helpers/verify_dpi_posting_calendar.sql"]
        scope = resolve_change_scope(
            [str(ROOT / p) for p in paths], reg=_reg()
        )
        self.assertTrue(scope["harness_only"])
        self.assertEqual([], scope["build_repos"])
        self.assertIn("dpic.posting_calendar_regression", scope["ntest_cases"])


class ServiceOnlyDpiTest(unittest.TestCase):
    def test_billing_java_minimal_cases(self) -> None:
        paths = [
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/dpi/dpibilling/DpiBillingBatchService.java",
        ]
        scope = resolve_change_scope(
            [str(ROOT / p) for p in paths], reg=_reg()
        )
        self.assertIn("batch.dpi_billing", scope["ntest_cases"])
        self.assertIn("dpic.ship_close_verify", scope["ntest_cases"])
        self.assertNotIn("dpic.posting_calendar_regression", scope["ntest_cases"])
        mods = scope["case_env"]["dpic.ship_close_verify"]["DPI_SHIP_MODULES"]
        self.assertIn("billing", mods)

    def test_booking_java_modules(self) -> None:
        blob = "dpiaccrualbookingbatchservice"
        mods = dpi_ship_modules(blob, {"dpiAccrualBooking"})
        self.assertIn("posting", mods)
        self.assertIn("eod", mods)


class ForeclosureServiceTest(unittest.TestCase):
    def test_foreclosure_processor_scoped(self) -> None:
        paths = [
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/foreclosure/processor/ChildLoanForeclosureProcessor.java",
        ]
        scope = resolve_change_scope(
            [str(ROOT / p) for p in paths], reg=_reg()
        )
        self.assertIn("foreclosure", scope["domains"])
        self.assertTrue(scope["build_repos"])


class CollapseTest(unittest.TestCase):
    def test_ship_close_subsumes_calendar(self) -> None:
        out = collapse_subsumed_cases(
            ["dpic.ship_close_verify", "dpic.posting_calendar_regression"]
        )
        self.assertEqual(["dpic.ship_close_verify"], out)


if __name__ == "__main__":
    unittest.main()
