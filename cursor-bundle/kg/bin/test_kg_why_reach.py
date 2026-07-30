#!/usr/bin/env python3
"""Unit tests for kg why/orient transitive failure-surface reachability."""
import importlib.util
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

BIN = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("kg_mod", BIN / "kg.py")
kg = importlib.util.module_from_spec(spec)
assert spec.loader
spec.loader.exec_module(kg)


def _mem_db():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.executescript("""
        CREATE TABLE nodes (id TEXT PRIMARY KEY, kind TEXT, label TEXT, json TEXT);
        CREATE TABLE edges (src_id TEXT, dst_id TEXT, rel TEXT, seq INTEGER, note TEXT, src TEXT);
    """)
    return c


class WhyReachTests(unittest.TestCase):
    def test_nested_internal_call_surfaces_child_diags(self):
        c = _mem_db()
        rows = [
            ("request:svc/parent", "request", "parent", "{}"),
            ("request:svc/child", "request", "child", "{}"),
            ("processor:parentProc", "processor", "parentProc", "{}"),
            ("processor:childProc", "processor", "childProc", "{}"),
            ("diag:curated.child", "diag", "child diag", '{"class":"ordering","label":"child"}'),
            ("diag:auto.ParentProc", "diag", "auto", '{"class":"silent_failure_surface","label":"auto"}'),
        ]
        c.executemany("INSERT INTO nodes VALUES (?,?,?,?)", rows)
        edges = [
            ("request:svc/parent", "processor:parentProc", "invokes", 1, "", ""),
            ("request:svc/child", "processor:childProc", "invokes", 1, "", ""),
            ("processor:parentProc", "request:svc/child", "calls", 0, "api_name", "java"),
            ("processor:childProc", "diag:curated.child", "has_failure_mode", 0, "", ""),
            ("processor:parentProc", "diag:auto.ParentProc", "has_failure_mode", 0, "", ""),
        ]
        c.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?)", edges)
        cur, auto, _, nested = kg._collect_flow_failure_diags(c, "request:svc/parent")
        self.assertIn("diag:curated.child", cur)
        self.assertIn("diag:auto.ParentProc", auto)
        self.assertIn("request:svc/child", nested)

    def test_related_diag_expansion(self):
        c = _mem_db()
        rows = [
            ("request:svc/r1", "request", "r1", "{}"),
            ("processor:p1", "processor", "p1", "{}"),
            ("diag:curated.a", "diag", "a", '{"class":"ordering"}'),
            ("diag:curated.b", "diag", "b", '{"class":"rounding"}'),
        ]
        c.executemany("INSERT INTO nodes VALUES (?,?,?,?)", rows)
        edges = [
            ("request:svc/r1", "processor:p1", "invokes", 1, "", ""),
            ("processor:p1", "diag:curated.a", "has_failure_mode", 0, "", ""),
            ("diag:curated.a", "diag:curated.b", "related", 0, "", ""),
        ]
        c.executemany("INSERT INTO edges VALUES (?,?,?,?,?,?)", edges)
        cur, _, _, _ = kg._collect_flow_failure_diags(c, "request:svc/r1")
        self.assertIn("diag:curated.a", cur)
        self.assertIn("diag:curated.b", cur)


if __name__ == "__main__":
    unittest.main()
