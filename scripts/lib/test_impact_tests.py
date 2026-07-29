#!/usr/bin/env python3
"""Tests for dynamic impact_tests KG blast-radius resolver."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from impact_tests import (  # noqa: E402
    build_plan,
    format_banner,
    impact_ran_satisfied,
    mark_ran,
)


class ImpactTestsDynamic(unittest.TestCase):
    def test_crn_processor_pulls_sibling_flows(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/"
            "transaction/processor/CreateTransactionMasterProcessor.java"
        )
        plan = build_plan(paths=[path], from_pending=False, draft_stubs=False)
        apis = {f["api"] for f in plan["flows"]}
        self.assertIn("postTransaction", apis)
        # sibling via shared write tables
        self.assertTrue(
            {"postManualJournalEntry", "glBalanceZeroisation", "doGLTransfer"} & apis,
            apis,
        )
        whys = "\n".join(plan.get("why_lines") or [])
        self.assertIn("writes", whys.lower())
        self.assertTrue(
            any("sibling" in w.lower() or "writes" in w.lower() for w in plan.get("why_lines") or []),
            plan.get("why_lines"),
        )

    def test_by_latest_harness_does_not_full_fc_dcf_suite(self) -> None:
        """TDPQA-207: scripts/testing/foreclosure/by-latest must not force-full FC+DCF."""
        import accounting_flow_domains as afd

        afd.load_domains.cache_clear()
        from impact_tests import _foreclosure_path_touch

        paths = [
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/"
            "loan/prepayment/dao/PrepaymentDetailsRepository.java",
            "scripts/testing/foreclosure/by-latest-details-api.sh",
            "scripts/testing/registry.json",
        ]
        self.assertFalse(_foreclosure_path_touch(paths))
        plan = build_plan(paths=paths, from_pending=False, draft_stubs=False, shipped_only=False)
        ordered = plan.get("ordered_cases") or []
        self.assertIn("foreclosure.by_latest_details_api", ordered)
        # Must NOT run full write/DCF suite on a read-path BY_LATEST ship
        for ban in (
            "dcf.vikram_fc_rstcre_dfc_e2e",
            "foreclosure.individual_child",
            "foreclosure.shg_bpi_parity",
            "flowtest.loan_prepayment_fc",
            "foreclosure.dpi_waiver_smoke",
        ):
            self.assertNotIn(ban, ordered, ordered)
        stats = plan.get("selection_tier_stats") or {}
        self.assertLessEqual(int(stats.get("full_count") or 99), 3, stats)
        self.assertLess(int(stats.get("wall_planned_s") or 9999), 400, stats)

    def test_mark_ran_fingerprint(self) -> None:
        path = "scripts/lib/impact_tests.py"
        plan = build_plan(paths=[path], from_pending=False, draft_stubs=False)
        mark_ran(plan)
        ok, msg = impact_ran_satisfied([path])
        self.assertTrue(ok, msg)


if __name__ == "__main__":
    unittest.main()
