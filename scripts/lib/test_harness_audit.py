#!/usr/bin/env python3
"""Unit checks for harness_audit — the gate that audits the other gates."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import harness_audit as ha  # noqa: E402


class MentionTests(unittest.TestCase):
    def test_matches_bare_filename(self):
        self.assertTrue(ha._mentions('bash "$ROOT/scripts/bin/foo-gate.sh" || exit 1', "foo-gate.sh"))

    def test_matches_python_module_stem(self):
        self.assertTrue(ha._mentions("import reuse_query_gate", "reuse_query_gate.py"))
        self.assertTrue(ha._mentions("from harness_fidelity_gate import check", "harness_fidelity_gate.py"))

    def test_path_prefix_does_not_block_match(self):
        self.assertTrue(ha._mentions("scripts/bin/query-plan-gate.sh", "query-plan-gate.sh"))

    def test_does_not_match_longer_sibling(self):
        self.assertFalse(ha._mentions("scripts/bin/query-plan-gate.sh", "plan-gate.sh"))
        self.assertFalse(ha._mentions("import reuse_query_gate_v2", "reuse_query_gate.py"))


class RegistryTests(unittest.TestCase):
    def test_missing_cmd_file_is_an_error(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts/testing").mkdir(parents=True)
            (root / "scripts/testing/registry.json").write_text(
                json.dumps({"a.case": {"cmd": "bash scripts/bin/does-not-exist.sh"}}),
                encoding="utf-8",
            )
            with mock.patch.object(ha, "ROOT", root):
                r = ha.check_registry()
        self.assertFalse(r["ok"])
        self.assertTrue(any("does-not-exist.sh" in e for e in r["errors"]))

    def test_live_registry_cmds_all_resolve(self):
        self.assertTrue(ha.check_registry()["ok"])


class WiringTests(unittest.TestCase):
    def test_unwired_gate_is_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts/bin").mkdir(parents=True)
            (root / "scripts/lib").mkdir(parents=True)
            (root / "scripts/bin/ship-loop-gate.sh").write_text("echo hi\n", encoding="utf-8")
            (root / "scripts/lib/lonely_gate.py").write_text("x = 1\n", encoding="utf-8")
            with mock.patch.object(ha, "ROOT", root):
                r = ha.check_wiring()
        self.assertFalse(r["ok"])
        self.assertIn("scripts/lib/lonely_gate.py", r["unwired"])

    def test_gate_reached_through_one_hop_is_wired(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts/bin").mkdir(parents=True)
            (root / "scripts/lib").mkdir(parents=True)
            (root / "scripts/bin/ship-loop-gate.sh").write_text(
                'bash "$ROOT/scripts/bin/wrapper.sh"\n', encoding="utf-8"
            )
            (root / "scripts/bin/wrapper.sh").write_text(
                "python3 scripts/lib/deep_gate.py\n", encoding="utf-8"
            )
            (root / "scripts/lib/deep_gate.py").write_text("x = 1\n", encoding="utf-8")
            with mock.patch.object(ha, "ROOT", root):
                r = ha.check_wiring()
        self.assertTrue(r["ok"], r.get("unwired"))

    def test_live_wiring_is_clean(self):
        self.assertTrue(ha.check_wiring()["ok"], ha.check_wiring().get("unwired"))


class OrphanTests(unittest.TestCase):
    def test_self_reference_does_not_rescue_an_orphan(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "scripts/bin").mkdir(parents=True)
            (root / "scripts/bin/alone.sh").write_text("# alone.sh usage\n", encoding="utf-8")
            with mock.patch.object(ha, "ROOT", root):
                r = ha.check_orphans()
        self.assertIn("scripts/bin/alone.sh", r["orphans"])


class HookTests(unittest.TestCase):
    def test_live_hooks_in_sync(self):
        r = ha.check_hooks()
        self.assertTrue(r["ok"], r.get("errors"))


if __name__ == "__main__":
    unittest.main()
