#!/usr/bin/env python3
"""Asking for state must be cheaper than building it, and must never invent it.

The second half is the one that matters. `run-the-real-thing-locally.md` allows seeding a
*precondition* and forbids seeding the *outcome*; a resolver that quietly fabricates a
near-match would turn every test built on it into a test of its own fixture.

    python3 scripts/lib/test_fixture_spec.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing" / "lib"))

import fixture_spec as fs  # noqa: E402


class MatchingTest(unittest.TestCase):
    """Pure predicate — no database."""

    def test_exact_child_count(self) -> None:
        kids = [("1", "ACTIVE"), ("2", "ACTIVE")]
        self.assertTrue(fs._matches(fs.FixtureSpec(children=2), kids))
        self.assertFalse(fs._matches(fs.FixtureSpec(children=3), kids))

    def test_child_state_requirement(self) -> None:
        kids = [("1", "ACTIVE"), ("2", "DISB_CNCL"), ("3", "ACTIVE")]
        self.assertTrue(fs._matches(fs.FixtureSpec(child_states={"DISB_CNCL": 1}), kids))
        self.assertFalse(fs._matches(fs.FixtureSpec(child_states={"DISB_CNCL": 2}), kids))

    def test_child_states_are_a_minimum_not_an_exact_split(self) -> None:
        kids = [("1", "DISB_CNCL"), ("2", "DISB_CNCL")]
        self.assertTrue(fs._matches(fs.FixtureSpec(child_states={"DISB_CNCL": 1}), kids))

    def test_no_constraints_matches_anything(self) -> None:
        self.assertTrue(fs._matches(fs.FixtureSpec(), [("1", "CLOSED")]))

    def test_describe_is_stable_for_logs(self) -> None:
        spec = fs.FixtureSpec(product="SHG", children=3, child_states={"DISB_CNCL": 1},
                              in_tenure=True)
        text = spec.describe()
        for token in ("product=SHG", "children=3", "DISB_CNCLx1", "in_tenure"):
            self.assertIn(token, text)


class NeverInventsTest(unittest.TestCase):

    def setUp(self) -> None:
        self._orig = fs._candidate_parents
        self.addCleanup(lambda: setattr(fs, "_candidate_parents", self._orig))

    def test_unsatisfiable_spec_returns_not_found_with_a_reason(self) -> None:
        fs._candidate_parents = lambda spec, limit=60: []
        got = fs.resolve(fs.FixtureSpec(children=9, child_states={"WRITOFF": 5}))
        self.assertFalse(got.found)
        self.assertTrue(got.why, "a miss must explain itself so the caller can skip honestly")
        self.assertEqual([], got.lans())

    def test_build_is_not_silently_faked(self) -> None:
        fs._candidate_parents = lambda spec, limit=60: []
        got = fs.resolve(fs.FixtureSpec(), allow_build=True)
        self.assertFalse(got.found, "allow_build must not conjure a LAN that does not exist")
        self.assertIn("disburse_loan_sanity", got.why)


class LiveResolutionTest(unittest.TestCase):
    """Against the real local DB — skipped when it is unreachable."""

    def setUp(self) -> None:
        if not fs._psql("SELECT 1;").strip():
            self.skipTest("local Yugabyte unreachable")

    def test_resolves_the_tdpqa72_shape_without_hand_building(self) -> None:
        got = fs.resolve(fs.FixtureSpec(loan_status="ACTIVE", children=3,
                                        child_states={"DISB_CNCL": 1}))
        if not got.found:
            self.skipTest("no group with a cancelled child in this local DB")
        self.assertTrue(got.parent_lan.isdigit())
        self.assertEqual(3, len(got.children))
        self.assertIn("DISB_CNCL", got.child_by_status)
        self.assertEqual("reused", got.source)
        self.assertEqual(4, len(got.lans()), "parent + 3 children")


if __name__ == "__main__":
    unittest.main(verbosity=2)
