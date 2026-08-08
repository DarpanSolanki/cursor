#!/usr/bin/env python3
"""Router must send every accounting task through the KG before source.

1929 shell greps were logged across 12 days; ~40-55% had a curated KG answer.
The cause was routing, not discipline: a prod perf regression classified as TEST
(because "batch job" matched above BUG/RCA) and CODE/DAO literally prescribed
grepping *Repository.java. These tests pin the shape, not the wording.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from agent_router import classify  # noqa: E402


class RouterKgFirstTest(unittest.TestCase):
    def test_perf_regression_is_not_classified_as_test(self):
        for text in (
            "IAC interestAccrualCalculation batch job took 2h45m in production after deploy",
            "loan EOD job slow after release",
            "billing job latency degraded on prod",
        ):
            self.assertEqual(classify(text)["classification"], "PERF_RCA", text)

    def test_perf_route_names_flow_and_skew_tooling(self):
        scripts = " ".join(classify("EOD batch job slow in production")["scripts"])
        self.assertIn("kg_flow", scripts)
        self.assertIn("batch_step_metrics.sql", scripts)
        self.assertIn("train-delta.sh", scripts)

    def test_accounting_analysis_reaches_rca_not_general(self):
        for text in (
            "why is parent accrued not matching children in SHG billing",
            "interest amount is wrong on the loan account",
            "GL posting shows duplicate entries",
            "installment due is zero after restructuring",
        ):
            self.assertEqual(classify(text)["classification"], "BUG/RCA", text)

    def test_kg_precedes_source_for_every_working_class(self):
        for text in (
            "disburseLoan stuck error 134207",
            "add a new @Query on loan_due_details repository",
            "run dcf sanity suite",
            "explain how disbursement works",
            "EOD job slow in production",
        ):
            scripts = classify(text)["scripts"]
            self.assertTrue(scripts, text)
            self.assertIn("kg_doctor", scripts[0], text)

    def test_dao_route_does_not_prescribe_grepping_repositories(self):
        scripts = " ".join(classify("add a new @Query on a repository")["scripts"])
        self.assertNotIn("grep *Repository", scripts)
        self.assertIn("kg_writes", scripts)

    def test_accounting_tasks_load_accounting_knowledge(self):
        for text in (
            "SHG accrued mismatch",
            "DPI billing wrong",
            "GL posting duplicate",
        ):
            self.assertIn("accounting-knowledge", classify(text)["skills"], text)

    def test_comms_stays_cheap(self):
        result = classify("draft an email to QA")
        self.assertEqual(result["classification"], "COMMS")
        self.assertEqual(result["scripts"], [])


if __name__ == "__main__":
    unittest.main()
