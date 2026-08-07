#!/usr/bin/env python3
"""A passing case with a violated money invariant must not report PASS.

The invariant logic itself is flowtest's and is tested there. What is new — and what
this asserts — is the *wiring*: that every money-tier registry case now runs it, that a
violation turns a green case red, and that a non-money case is left alone.

Without this, adding the guard would look like coverage while doing nothing.

    python3 scripts/lib/test_money_invariants_wiring.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing" / "lib"))

import money_invariants as mi  # noqa: E402


class _Raising:
    @staticmethod
    def snapshot_invariants(lans):
        return {lan: {} for lan in lans}

    @staticmethod
    def run_universal_invariants(lans, **kw):
        raise AssertionError("GL imbalance 12.00 on 6000000001")


class _Clean:
    @staticmethod
    def snapshot_invariants(lans):
        return {lan: {} for lan in lans}

    @staticmethod
    def run_universal_invariants(lans, **kw):
        return {"ok": True}


class MoneyInvariantWiringTest(unittest.TestCase):

    def setUp(self) -> None:
        self._orig = mi._invariants
        self.addCleanup(lambda: setattr(mi, "_invariants", self._orig))

    def test_violation_turns_a_green_case_red(self) -> None:
        mi._invariants = lambda: _Raising()
        self.assertFalse(mi.verify(["6000000001"], {"lans": {}}, label="t"))

    def test_clean_run_passes(self) -> None:
        mi._invariants = lambda: _Clean()
        self.assertTrue(mi.verify(["6000000001"], {"lans": {}}, label="t"))

    def test_non_money_case_is_not_guarded(self) -> None:
        guard = mi.Guard({"smoke_tier": "service"}, case_id="x")
        self.assertFalse(guard.enabled)
        self.assertTrue(guard.check(), "a non-money case must never be failed by this")

    def test_money_case_is_guarded(self) -> None:
        guard = mi.Guard({"smoke_tier": "money", "defaults": {"LAN": "6000000001"}}, case_id="x")
        self.assertTrue(guard.enabled)
        self.assertEqual(["6000000001"], guard.lans)

    def test_lan_discovery_reads_defaults_env_and_overlay(self) -> None:
        case = {
            "defaults": {"PARENT_LAN": "6000000001", "NOT_A_LAN": "hello"},
            "env": {"CHILD2_LAN": "6000000002"},
        }
        found = mi.declared_lans(case, {"VICTIM_LAN": "6000000003"})
        self.assertEqual(["6000000001", "6000000002", "6000000003"], found)
        self.assertNotIn("hello", found)

    def test_short_or_nonnumeric_values_are_not_treated_as_lans(self) -> None:
        self.assertEqual([], mi.declared_lans({"defaults": {"LAN": "abc"}}))
        self.assertEqual([], mi.declared_lans({"defaults": {"LAN": "12"}}))

    def test_no_lans_never_fails_a_case(self) -> None:
        mi._invariants = lambda: _Raising()
        self.assertTrue(mi.verify([], None, label="t"),
                        "with nothing to check the guard must stay silent, not fail")

    def test_ntest_wraps_both_case_runners(self) -> None:
        text = (ROOT / "scripts/testing/ntest.py").read_text(encoding="utf-8")
        for fn in ("def _run_api_case(", "def _run_flow_case("):
            self.assertIn(fn, text)
            body = text[text.index(fn):]
            self.assertIn("_money_guard", body[:600],
                          f"{fn} must run the money guard, or 93 money cases inherit nothing")


if __name__ == "__main__":
    unittest.main(verbosity=2)
