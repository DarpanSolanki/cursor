#!/usr/bin/env python3
"""Tests for ship_discipline_gate impact_analysis requirement."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import ship_discipline_gate as g  # noqa: E402


def _full_impact() -> dict:
    return {
        "entry_paths": "deathForeclosureInsuranceJob; loanDeathForeclosure",
        "scenario_modes": "last-child; non-last; standalone Out-of-scope replay",
        "callers": "DeathForeclosureInsuranceWriter.doParentPartPrePayment grep",
        "downstream": "getLoanAccountSummaryDetails; GL BILLING; registry dcf.group_parent_last_child_e2e",
        "modes": "N/A payment modes — DFC batch only",
        "account_field": "loan_account.status parent+child",
        "error_codes": "none new — existing DFC errors",
        "happy_path": "SHG last-child EXTRA=0 still passes",
        "blast_radius": "parent RSCH + child DFC writers only",
        "out_of_scope": "standalone individual DFC — evidence: separate registry case",
    }


class ImpactAnalysisTest(unittest.TestCase):
    def test_money_tier_requires_all_keys(self) -> None:
        disc = {"impact_analysis": _full_impact()}
        errors = g._check_impact_analysis(disc)
        self.assertEqual(errors, [])

    def test_missing_impact_block_fails(self) -> None:
        errors = g._check_impact_analysis({})
        self.assertTrue(any("missing impact_analysis" in e for e in errors))

    def test_short_field_fails(self) -> None:
        impact = _full_impact()
        impact["callers"] = "short"
        errors = g._check_impact_analysis({"impact_analysis": impact})
        self.assertTrue(any("impact_analysis.callers" in e for e in errors))

    def test_service_accounting_repo_needs_impact(self) -> None:
        pending = {
            "tier": "service",
            "repos": ["trustt-platform-accounting"],
            "files": ["trustt-platform-accounting/src/FooProcessor.java"],
        }
        self.assertTrue(g._needs_impact_analysis(pending, {}))

    def test_workspace_tier_skips_impact(self) -> None:
        pending = {"tier": "workspace", "files": ["scripts/bin/foo.sh"]}
        self.assertFalse(g._needs_impact_analysis(pending, {}))


class CheckIntegrationTest(unittest.TestCase):
    def test_check_fails_without_impact_on_money_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            pending = {
                "tier": "money",
                "updated_at": "2026-07-22T00:00:00Z",
                "files": ["trustt-platform-accounting/src/in/novopay/loan/Foo.java"],
                "repos": ["trustt-platform-accounting"],
            }
            (cursor / ".pending-ship-work.json").write_text(json.dumps(pending), encoding="utf-8")
            disc = {
                "pending_updated_at": pending["updated_at"],
                "minimal_fix": "Fix parent force-bill slice for any-child DFC",
                "read_path_change": "No",
                "hot_path_scan": "PASS",
                "verify_mode": "RUNTIME_VERIFIED",
                "kg_enrichment": "CASES",
                "assumptions": [],
            }
            (cursor / ".ship-discipline.json").write_text(json.dumps(disc), encoding="utf-8")
            with mock.patch.object(g, "ROOT", root), mock.patch.object(g, "PENDING", cursor / ".pending-ship-work.json"), mock.patch.object(
                g, "DISCIPLINE", cursor / ".ship-discipline.json"
            ), mock.patch("subprocess.run") as mrun:
                mrun.return_value = mock.Mock(returncode=0, stdout="", stderr="")
                with mock.patch("reuse_query_gate.check", return_value=[]):
                    rc = g.check(hard=True)
            self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
