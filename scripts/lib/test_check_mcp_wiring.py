#!/usr/bin/env python3
"""Tests for check-mcp-wiring file contract + IDE catalog gate."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import mcp_wiring_gate as cmw  # noqa: E402


class FileContractTest(unittest.TestCase):
    def test_trustt_only_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mcp = root / ".mcp.json"
            mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "trustt-kg": {
                                "command": "python3",
                                "args": ["cursor-bundle/kg/mcp/kg_mcp_server.py"],
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )
            (root / "cursor-bundle/kg/mcp").mkdir(parents=True)
            (root / "cursor-bundle/kg/mcp/kg_mcp_server.py").write_text("# stub\n")
            with mock.patch.object(cmw, "ROOT", root):
                err, servers = cmw.check_file_contract(mcp)
            self.assertEqual([], err)
            self.assertIn("trustt-kg", servers)

    def test_rejects_project_atlassian_and_sse(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            mcp = root / ".mcp.json"
            mcp.write_text(
                json.dumps(
                    {
                        "mcpServers": {
                            "trustt-kg": {
                                "command": "python3",
                                "args": ["x.py"],
                            },
                            "atlassian": {
                                "type": "sse",
                                "url": "https://mcp.atlassian.com/v1/sse",
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.object(cmw, "ROOT", root):
                err, _ = cmw.check_file_contract(mcp)
            blob = " ".join(err)
            self.assertIn("must not declare Atlassian", blob)
            self.assertIn("legacy SSE", blob)


class IdeCatalogTest(unittest.TestCase):
    def _mk_server(self, mcps: Path, name: str, tools: list[str]) -> Path:
        d = mcps / name
        (d / "tools").mkdir(parents=True)
        (d / "SERVER_METADATA.json").write_text(
            json.dumps({"serverIdentifier": name, "serverName": name}), encoding="utf-8"
        )
        for t in tools:
            (d / "tools" / f"{t}.json").write_text("{}", encoding="utf-8")
        return d

    def test_missing_trustt_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            projects = Path(td) / "projects"
            slug = cmw._workspace_project_slug(root)
            mcps = projects / slug / "mcps"
            mcps.mkdir(parents=True)
            self._mk_server(mcps, "plugin-atlassian-atlassian", [f"t{i}" for i in range(10)])
            with mock.patch.object(cmw, "ROOT", root), mock.patch.object(
                cmw, "CURSOR_PROJECTS", projects
            ):
                err, _ = cmw.check_ide_catalog(root)
            self.assertTrue(any("trustt-kg" in e for e in err))

    def test_healthy_catalog_ok(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            projects = Path(td) / "projects"
            slug = cmw._workspace_project_slug(root)
            mcps = projects / slug / "mcps"
            mcps.mkdir(parents=True)
            kg_tools = ["kg_doctor"] + [f"kg_t{i}" for i in range(20)]
            self._mk_server(mcps, "project-0-sliProd-trustt-kg", kg_tools)
            self._mk_server(
                mcps, "plugin-atlassian-atlassian", [f"jira{i}" for i in range(10)]
            )
            with mock.patch.object(cmw, "ROOT", root), mock.patch.object(
                cmw, "CURSOR_PROJECTS", projects
            ):
                err, warn = cmw.check_ide_catalog(root)
            self.assertEqual([], err)
            self.assertEqual([], warn)

    def test_duplicate_atlassian_warns(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            projects = Path(td) / "projects"
            slug = cmw._workspace_project_slug(root)
            mcps = projects / slug / "mcps"
            mcps.mkdir(parents=True)
            kg_tools = ["kg_doctor"] + [f"kg_t{i}" for i in range(20)]
            self._mk_server(mcps, "project-0-sliProd-trustt-kg", kg_tools)
            self._mk_server(mcps, "plugin-atlassian-atlassian", [f"a{i}" for i in range(10)])
            self._mk_server(mcps, "project-0-sliProd-atlassian", [f"b{i}" for i in range(10)])
            with mock.patch.object(cmw, "ROOT", root), mock.patch.object(
                cmw, "CURSOR_PROJECTS", projects
            ):
                err, warn = cmw.check_ide_catalog(root)
            self.assertEqual([], err)
            self.assertTrue(any("BOTH" in w or "duplicate" in w.lower() for w in warn))


if __name__ == "__main__":
    unittest.main()
