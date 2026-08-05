#!/usr/bin/env python3
"""The universal-invariants gate must be capable of FAILING.

It shipped as a money-tier case that took `baseline = snapshot_invariants(lans)`
moments before comparing against it, so every baseline-delta check was neutralised
and the case passed on any state. These tests pin the two properties that keep it
honest: absolute invariants still fire, and a self-snapshot baseline is rejected.
"""
from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/testing"))

from flowtest import invariants as inv  # noqa: E402

LAN = "TESTLAN0001"

CLEAN_SNAPSHOT = {
    "lans": {
        LAN: {
            "gl_imbalance": Decimal("0"),
            "unbalanced_refs": [],
            "air_delta": Decimal("0"),
            "bpi_air": Decimal("0"),
            "neg_dues": 0,
            "orphan_dues": 0,
            "excess": Decimal("0"),
            "loan_status": "ACTIVE",
            "account_status": "ACTIVE",
        }
    }
}


def _patched(snapshot, *, imbalances=None, air=Decimal("0")):
    return [
        mock.patch.object(inv, "snapshot_invariants", return_value=snapshot),
        mock.patch.object(inv, "all_success_txn_refs", return_value=["ref1"]),
        mock.patch.object(inv, "per_ref_gl_imbalances", return_value=imbalances or {}),
        mock.patch.object(inv, "scope_gl_totals", return_value=(Decimal("100"), Decimal("100"))),
        mock.patch.object(inv, "fc_settlement_air_delta", return_value=(air, ["r"])),
        mock.patch.object(inv, "bpi_air_credit_after_force_bill", return_value=Decimal("0")),
        mock.patch.object(inv, "INVARIANTS_OFF", False),
        mock.patch.object(inv, "ACCEPTANCE_STRICT", True),
    ]


class AbsoluteInvariantsFire(unittest.TestCase):
    def _run(self, snapshot, **kw):
        patches = _patched(snapshot, **kw.pop("patch", {}))
        for p in patches:
            p.start()
        self.addCleanup(lambda: [p.stop() for p in patches])
        return inv.run_universal_invariants([LAN], baseline=None, absolute_only=True)

    def test_clean_state_passes(self):
        r = self._run(CLEAN_SNAPSHOT)
        self.assertTrue(r["ok"], r.get("failures"))

    def test_per_txn_gl_imbalance_fails(self):
        with self.assertRaises(AssertionError) as ctx:
            self._run(CLEAN_SNAPSHOT, patch={"imbalances": {"ref1": Decimal("5")}})
        self.assertIn("GL per-txn", str(ctx.exception))

    def test_negative_dues_fail(self):
        snap = {"lans": {LAN: {**CLEAN_SNAPSHOT["lans"][LAN], "neg_dues": 2}}}
        with self.assertRaises(AssertionError) as ctx:
            self._run(snap)
        self.assertIn("negative-dues", str(ctx.exception))

    def test_orphan_dues_fail(self):
        snap = {"lans": {LAN: {**CLEAN_SNAPSHOT["lans"][LAN], "orphan_dues": 3}}}
        with self.assertRaises(AssertionError) as ctx:
            self._run(snap)
        self.assertIn("dues", str(ctx.exception))

    def test_illegal_status_fails(self):
        snap = {"lans": {LAN: {**CLEAN_SNAPSHOT["lans"][LAN], "loan_status": "CLOSED",
                               "account_status": "ACTIVE"}}}
        with self.assertRaises(AssertionError) as ctx:
            self._run(snap)
        self.assertIn("status", str(ctx.exception))

    def test_negative_excess_fails(self):
        snap = {"lans": {LAN: {**CLEAN_SNAPSHOT["lans"][LAN], "excess": Decimal("-9")}}}
        with self.assertRaises(AssertionError) as ctx:
            self._run(snap)
        self.assertIn("excess", str(ctx.exception))

    def test_midflow_air_delta_does_not_fail_absolute_mode(self):
        r = self._run(CLEAN_SNAPSHOT, patch={"air": Decimal("1381")})
        self.assertTrue(r["ok"], "bundle AIR delta is flow-relative, not absolute")


class GateRunnerIsNotVacuous(unittest.TestCase):
    def test_runner_does_not_self_baseline(self):
        src = (ROOT / "scripts/testing/flowtest/run_universal_invariants_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn(
            "baseline=baseline",
            src,
            "self-snapshot baseline neutralises every delta invariant — gate becomes vacuous",
        )
        self.assertIn("absolute_only=True", src)

    def test_runner_fails_when_skipped(self):
        src = (ROOT / "scripts/testing/flowtest/run_universal_invariants_gate.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("skipped", src)
        self.assertIn("return 1", src)


if __name__ == "__main__":
    unittest.main()
