"""The `file_exists` / `file_row_count` expect keys: the harness's only way to prove an
EOD/BOD report job wrote a real file, not just that it returned HTTP 2xx.

Every check here is fail-closed on the two failure modes those 56 jobs actually have:
a job that never writes the file (absent path), and a job that writes nothing this run
because a prior local run already left the file there (stale mtime). A rule that passes
on either is worse than no rule — it reports proof that was never taken.

    python3 scripts/lib/test_file_assert.py
"""
from __future__ import annotations

import pathlib
import sys
import tempfile
import time
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

from lib.assertions import run_assertions
from lib.api_client import ApiResult
from lib.expect import expand_expect


def make_result() -> ApiResult:
    return ApiResult(
        api_name="x", url="http://x", http_status=200,
        body='{"response_status":{"code":"0","status":"SUCCESS"}}', elapsed_ms=1)


class ExpandExpectTest(unittest.TestCase):

    def test_file_exists_single_path_expands_to_one_rule(self) -> None:
        rules = expand_expect({"file_exists": "/tmp/foo.csv"})
        file_rules = [r for r in rules if r["type"] == "file_exists"]
        self.assertEqual(len(file_rules), 1)
        self.assertEqual(file_rules[0]["path"], "/tmp/foo.csv")

    def test_file_exists_list_expands_to_multiple_rules(self) -> None:
        rules = expand_expect({"file_exists": ["/tmp/a.csv", "/tmp/b.csv"]})
        file_rules = [r for r in rules if r["type"] == "file_exists"]
        self.assertEqual(len(file_rules), 2)

    def test_file_row_count_carries_min(self) -> None:
        rules = expand_expect({"file_row_count": {"path": "/tmp/foo.csv", "min": 5}})
        row_rules = [r for r in rules if r["type"] == "file_row_count"]
        self.assertEqual(row_rules[0]["min"], 5)

    def test_file_row_count_defaults_min_to_one(self) -> None:
        rules = expand_expect({"file_row_count": {"path": "/tmp/foo.csv"}})
        row_rules = [r for r in rules if r["type"] == "file_row_count"]
        self.assertEqual(row_rules[0]["min"], 1)


class FileExistsAssertionTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_case(self, path: str, cutoff: float | None):
        result = make_result()
        rule = {"type": "file_exists", "name": "f", "path": path}
        env = {} if cutoff is None else {"NTEST_RUN_STARTED_AT": str(cutoff)}
        spec = {"assertions": [rule]}
        return run_assertions(result.body, result, spec, env=env)

    def test_fresh_nonempty_file_passes(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "report.csv"
        f.write_text("HDR|1\nROW|a\n")
        run = self.run_case(str(f), cutoff)
        self.assertTrue(run.passed, run.results[0].detail)

    def test_absent_file_fails(self) -> None:
        run = self.run_case(str(self.dir / "missing.csv"), time.time())
        self.assertFalse(run.passed)
        self.assertIn("no file matched", run.results[0].detail)

    def test_stale_file_from_prior_run_fails(self) -> None:
        f = self.dir / "report.csv"
        f.write_text("HDR|1\nROW|a\n")
        cutoff = time.time() + 5
        run = self.run_case(str(f), cutoff)
        self.assertFalse(run.passed)
        self.assertIn("none fresh", run.results[0].detail)

    def test_fresh_but_empty_file_fails(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "report.csv"
        f.write_text("")
        run = self.run_case(str(f), cutoff)
        self.assertFalse(run.passed)

    def test_missing_freshness_marker_fails_closed(self) -> None:
        f = self.dir / "report.csv"
        f.write_text("HDR|1\n")
        run = self.run_case(str(f), None)
        self.assertFalse(run.passed)
        self.assertIn("NTEST_RUN_STARTED_AT", run.results[0].detail)

    def test_glob_pattern_matches_dated_filename(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "CIC_MEMBER_20260807.csv"
        f.write_text("HDR|1\n")
        pattern = str(self.dir / "CIC_MEMBER_*.csv")
        run = self.run_case(pattern, cutoff)
        self.assertTrue(run.passed, run.results[0].detail)

    def test_var_expansion_in_path(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "report_20260807.csv"
        f.write_text("HDR|1\n")
        rule = {"type": "file_exists", "name": "f", "path": str(self.dir / "report_${DATE}.csv")}
        result = make_result()
        env = {"NTEST_RUN_STARTED_AT": str(cutoff), "DATE": "20260807"}
        spec = {"assertions": [rule]}
        run = run_assertions(result.body, result, spec, env=env)
        self.assertTrue(run.passed, run.results[0].detail)


class FileRowCountAssertionTest(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = pathlib.Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_case(self, path: str, minimum: int, cutoff: float | None):
        result = make_result()
        rule = {"type": "file_row_count", "name": "rc", "path": path, "min": minimum}
        env = {} if cutoff is None else {"NTEST_RUN_STARTED_AT": str(cutoff)}
        spec = {"assertions": [rule]}
        return run_assertions(result.body, result, spec, env=env)

    def test_row_count_meets_min_passes(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "report.csv"
        f.write_text("HDR\nROW1\nROW2\nEOF\n")
        run = self.run_case(str(f), 3, cutoff)
        self.assertTrue(run.passed, run.results[0].detail)

    def test_row_count_below_min_fails(self) -> None:
        cutoff = time.time()
        time.sleep(0.05)
        f = self.dir / "report.csv"
        f.write_text("HDR\nEOF\n")
        run = self.run_case(str(f), 10, cutoff)
        self.assertFalse(run.passed)
        self.assertIn("rows=2", run.results[0].detail)

    def test_stale_file_fails_even_if_row_count_would_pass(self) -> None:
        f = self.dir / "report.csv"
        f.write_text("HDR\nROW1\nROW2\nROW3\nEOF\n")
        cutoff = time.time() + 5
        run = self.run_case(str(f), 1, cutoff)
        self.assertFalse(run.passed)

    def test_missing_file_fails(self) -> None:
        run = self.run_case(str(self.dir / "missing.csv"), 1, time.time())
        self.assertFalse(run.passed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
