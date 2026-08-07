#!/usr/bin/env python3
"""Per-domain coverage ratchet — proven to fail when a domain goes backwards.

The workspace had one coverage ratchet and it counted money APIs, so `read_api` (555 APIs,
1 covered) and the accounting `write_ops` domain (45 APIs, 0 covered) could rot with nothing
reporting a direction.

    python3 scripts/lib/test_domain_coverage_gate.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import domain_coverage_gate as dcg  # noqa: E402


class MeasureTest(unittest.TestCase):

    def setUp(self) -> None:
        self.now = dcg.measure()

    def test_both_dimensions_are_present(self) -> None:
        cats = [k for k in self.now if k.startswith("category:")]
        doms = [k for k in self.now if k.startswith("domain:")]
        self.assertGreater(len(cats), 10, "platform categories missing")
        self.assertGreater(len(doms), 10, "accounting flow domains missing")

    def test_no_domain_reports_a_silent_zero_total(self) -> None:
        empty = [k for k, v in self.now.items() if v["total"] == 0]
        self.assertLessEqual(
            len(empty), 3,
            f"a domain with total=0 measures nothing and can never move: {empty}")

    def test_gaps_never_exceed_total(self) -> None:
        for key, v in self.now.items():
            self.assertLessEqual(v["gaps"], v["total"], key)

    def test_accounting_domains_report_real_coverage_not_zero(self) -> None:
        doms = {k: v for k, v in self.now.items() if k.startswith("domain:")}
        covered = sum(1 for v in doms.values() if v["total"] - v["gaps"] > 0)
        self.assertGreater(
            covered, 5,
            "every accounting domain showed 0 covered because coverage_report() defaulted "
            "its registry argument to {} — a false zero, not a real gap")

    def test_read_inquiry_matches_the_standalone_report(self) -> None:
        """The gate and accounting-flow-coverage.sh must not disagree."""
        sys.path.insert(0, str(ROOT / "scripts" / "lib"))
        import accounting_flow_domains as afd
        rows = {r["domain"]: r for r in afd.coverage_report()}
        for name, row in rows.items():
            key = f"domain:{name}"
            if key not in self.now:
                continue
            self.assertEqual(row["gap"], self.now[key]["gaps"], f"{key} disagrees")


class RatchetTest(unittest.TestCase):

    def test_a_domain_going_backwards_is_a_regression(self) -> None:
        base = {"category:read_api": {"total": 555, "gaps": 500}}
        now = {"category:read_api": {"total": 555, "gaps": 510}}
        regressions, grew, _ = dcg.compare(now, base)
        self.assertTrue(regressions, "coverage fell and the ratchet stayed silent")
        self.assertEqual([], grew)

    def test_improvement_is_accepted_and_lowers_the_baseline(self) -> None:
        base = {"d": {"total": 100, "gaps": 90}}
        now = {"d": {"total": 100, "gaps": 80}}
        regressions, _, merged = dcg.compare(now, base)
        self.assertEqual([], regressions)
        self.assertEqual(80, merged["d"]["gaps"])

    def test_growth_from_new_apis_is_reported_not_failed(self) -> None:
        base = {"d": {"total": 100, "gaps": 90}}
        now = {"d": {"total": 130, "gaps": 115}}
        regressions, grew, _ = dcg.compare(now, base)
        self.assertEqual([], regressions, "a rescan finding new APIs is not a regression")
        self.assertTrue(grew)

    def test_a_new_domain_is_adopted_without_failing(self) -> None:
        regressions, _, merged = dcg.compare({"fresh": {"total": 5, "gaps": 5}}, {})
        self.assertEqual([], regressions)
        self.assertIn("fresh", merged)

    def test_holding_is_not_a_regression(self) -> None:
        base = now = {"d": {"total": 10, "gaps": 4}}
        self.assertEqual([], dcg.compare(now, base)[0])


class LiveBaselineTest(unittest.TestCase):

    def test_the_live_workspace_holds(self) -> None:
        regressions, _, _ = dcg.compare(dcg.measure(), dcg.load_baseline())
        self.assertEqual([], regressions, "\n".join(regressions))


if __name__ == "__main__":
    unittest.main(verbosity=2)
