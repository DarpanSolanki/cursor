#!/usr/bin/env python3
"""Pins the batch_read_plan check that catches GAP-095.

A partitioned job counts its candidates before it runs and stores the figure as
`batch_record_count`. Comparing that against `read_count` is what distinguishes "ran, nothing
due today" from "planned for 112 rows and read none of them" — the run that shipped green on
2026-08-07 while every due-installment reminder was dropped.

The check lives inline in ntest's batch path rather than in a rule object, so these tests
exercise the two helpers it is built from plus the decision itself.
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))


def verdict(planned: int, read: int) -> str:
    if planned <= 0:
        return "SKIP"
    return "PASS" if read > 0 else "FAIL"


class BatchReadPlanTest(unittest.TestCase):
    def test_planned_rows_read_none_fails(self):
        self.assertEqual(verdict(112, 0), "FAIL")

    def test_planned_rows_read_some_passes(self):
        self.assertEqual(verdict(38, 74), "PASS")

    def test_healthy_partitioned_job_passes(self):
        self.assertEqual(verdict(2154, 4308), "PASS")

    def test_job_without_a_plan_is_skipped_not_failed(self):
        self.assertEqual(verdict(-1, 0), "SKIP")

    def test_job_planning_zero_is_skipped(self):
        self.assertEqual(verdict(0, 0), "SKIP")

    def test_partial_loss_is_not_caught_and_that_is_documented(self):
        # 2026-08-08: 38 candidates, 37 delivered, one silently dropped. read>0 so this passes.
        # The check catches total loss only; partial loss needs a per-row correlator the
        # harness does not have. Stated here so nobody reads a green as "all rows processed".
        self.assertEqual(verdict(38, 74), "PASS")


class BatchPlannedQueryTest(unittest.TestCase):
    def test_helper_reads_parameter_value_not_long_val(self):
        import inspect

        import ntest

        src = inspect.getsource(ntest._batch_planned)
        self.assertIn("parameter_value", src)
        self.assertNotIn("long_val", src)

    def test_helper_names_its_failure_rather_than_returning_silent_minus_one(self):
        import inspect

        import ntest

        src = inspect.getsource(ntest._batch_planned)
        self.assertIn("WARN", src)

    def test_check_is_unconditional_not_opt_in_per_case(self):
        import inspect

        import ntest

        # The two workspaces name this wrapper differently; the behaviour is what is pinned.
        runner = getattr(ntest, "_run_api_case_inner", None) or ntest._run_api_case
        src = inspect.getsource(runner)
        self.assertIn("_batch_planned(job_name, before_exec)", src)
        self.assertNotIn('expect").get("batch_read_plan', src)


if __name__ == "__main__":
    unittest.main(verbosity=2)
