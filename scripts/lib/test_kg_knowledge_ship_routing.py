#!/usr/bin/env python3
"""L1/L2: KG harness paths are knowledge-only; sticky money pending must not force DPIC."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from infer_ship_apis import (  # noqa: E402
    build_impact,
    classify_path,
    is_knowledge_only_paths,
    is_knowledge_path,
)
from ship_push_gate import should_skip_auto_close_for_knowledge_head  # noqa: E402


class KgKnowledgeShipRoutingTest(unittest.TestCase):
    def test_kg_scripts_are_knowledge(self) -> None:
        paths = [
            "cursor-bundle/kg/bin/kg.py",
            "cursor-bundle/kg/mcp/kg_mcp_server.py",
            "scripts/bin/kg-align.sh",
            "scripts/bin/kg-switch.sh",
            "scripts/bin/kg-self-enhance.sh",
            "scripts/lib/kg_state_banner.py",
            ".cursor/changelog.md",
        ]
        for p in paths:
            self.assertTrue(is_knowledge_path(p), p)
        self.assertTrue(is_knowledge_only_paths(paths))
        self.assertEqual(build_impact([str(ROOT / p) for p in paths])["tier"], "workspace")

    def test_money_java_not_knowledge(self) -> None:
        p = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan/"
            "prepayment/dao/PrepaymentDetailsRepository.java"
        )
        self.assertFalse(is_knowledge_path(p))
        self.assertEqual(classify_path(p), "money")

    def test_knowledge_head_skips_even_with_sticky_money_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            pending = {
                "tier": "money",
                "files": [
                    "trustt-platform-accounting/src/main/java/Foo.java",
                    "scripts/bin/kg-align.sh",
                ],
                "apis": ["getLoanForeclosureDetails"],
                "repos": ["trustt-platform-accounting"],
            }
            (cursor / ".pending-ship-work.json").write_text(
                json.dumps(pending), encoding="utf-8"
            )
            with mock.patch("ship_push_gate.ROOT", root), mock.patch(
                "ship_push_gate.is_knowledge_only_head", return_value=True
            ):
                self.assertTrue(should_skip_auto_close_for_knowledge_head(root))
            # knowledge path pruned from pending
            left = json.loads((cursor / ".pending-ship-work.json").read_text(encoding="utf-8"))
            self.assertNotIn("scripts/bin/kg-align.sh", left.get("files") or [])
            self.assertIn(
                "trustt-platform-accounting/src/main/java/Foo.java",
                left.get("files") or [],
            )


if __name__ == "__main__":
    unittest.main()
