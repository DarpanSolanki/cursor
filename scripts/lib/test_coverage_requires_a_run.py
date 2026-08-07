"""Coverage means a case that ran, not a case that exists (GAP-090).

`has_proof` used to be `registry_cases or unit_tests or ...` — pure membership. An API left
the gap column the moment someone listed a case against it, whether or not it had ever
executed. 46 of 70 "covered" APIs had no footprint at all, so every coverage figure in the
workspace was optimistic by an unknown amount.

This is the presence-only defect one level up: `40-knowledge-upkeep.md` rejects `>= 0` as an
assert for the same reason it must reject "a case is listed" as coverage.

    python3 scripts/lib/test_coverage_requires_a_run.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
sys.path.insert(0, str(ROOT / "scripts" / "testing"))


def rows() -> list[dict]:
    path = FLOW / "test_coverage.jsonl"
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


class ProofIsNotMembershipTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = rows()
        if not self.rows:
            self.skipTest("coverage matrix not built")

    def test_the_matrix_reports_both_and_they_are_not_the_same_field(self) -> None:
        row = self.rows[0]
        self.assertIn("has_case", row, "membership must stay visible, just renamed")
        self.assertIn("has_proof", row)

    def test_proof_never_exceeds_membership(self) -> None:
        proof = sum(1 for r in self.rows if r.get("has_proof"))
        case = sum(1 for r in self.rows if r.get("has_case"))
        self.assertLessEqual(proof, case,
                             "an API cannot be proven without a case that names it")

    def test_a_listed_but_unrun_case_is_still_a_gap(self) -> None:
        listed_unproven = [r for r in self.rows
                           if r.get("has_case") and not r.get("has_proof")
                           and r.get("scope") != "out"]
        for r in listed_unproven:
            self.assertTrue(
                r.get("gaps"),
                f"{r['api']}: a case is listed, nothing ran, and no gap is reported")

    def test_proof_implies_a_run_or_a_verified_footprint(self) -> None:
        for r in self.rows:
            if not r.get("has_proof"):
                continue
            self.assertTrue(
                r.get("run_status") == "run_verified" or r.get("footprint_best") == "verified",
                f"{r['api']}: has_proof without a green run or a verified footprint")

    def test_membership_alone_is_not_treated_as_coverage(self) -> None:
        """The regression this file exists to prevent."""
        gap_free = [r for r in self.rows
                    if not r.get("gaps") and r.get("scope") != "out"]
        unproven = [r for r in gap_free if not r.get("has_proof")]
        self.assertEqual([], [r["api"] for r in unproven][:10],
                         "APIs with no gap and no proof — membership counted as coverage again")


class TrainAwarenessTest(unittest.TestCase):
    """A case that cannot run here is not a case nobody ran."""

    def test_a_train_inapplicable_case_is_not_reported_as_never_run(self) -> None:
        import run_evidence
        inapplicable = run_evidence.inapplicable_cases()
        if not inapplicable:
            self.skipTest("every registry case is applicable on this checkout")
        for r in rows():
            if "case_never_ran" not in (r.get("gaps") or []):
                continue
            cases = set(r.get("registry_cases") or []) | set(r.get("ntest_cases") or [])
            self.assertTrue(
                cases - inapplicable,
                f"{r['api']}: every case needs paths absent from this train, so it is "
                "blamed for coverage the branch cannot provide")

    def test_the_public_alias_exists(self) -> None:
        import run_evidence
        self.assertTrue(callable(run_evidence.inapplicable_cases))


if __name__ == "__main__":
    unittest.main(verbosity=2)
