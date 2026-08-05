#!/usr/bin/env python3
"""Unit checks for local_parity_gate (Upgrade 8 TASK E)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import local_parity_gate as g


class LocalParityTests(unittest.TestCase):
    def test_skip_when_no_schema(self):
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(g, "HAND_PATCH_LOG", Path(td) / "hand.jsonl"):
                r = g.check_parity(
                    {"files": ["scripts/testing/foo.py"], "updated_at": "2026-07-22T12:00:00Z"}
                )
        self.assertTrue(r["ok"])
        self.assertTrue(r.get("skipped"))
        self.assertIn("n/a", r["summary"])

    def test_temp_table_ddl_is_not_a_money_hand_patch(self):
        sql = (
            "DROP TABLE IF EXISTS _dpi_txn_purge_ids;\n"
            "CREATE TEMP TABLE _dpi_txn_purge_ids AS SELECT id FROM mfi_accounting.loan_account;\n"
            "DELETE FROM mfi_accounting.loan_due_details WHERE id IN (SELECT id FROM _dpi_txn_purge_ids);\n"
        )
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(g, "HAND_PATCH_LOG", Path(td) / "hand.jsonl"):
                self.assertIsNone(g.log_hand_patch(sql=sql, source="test", path="purge.sql"))

    def test_real_money_ddl_is_logged(self):
        sql = "ALTER TABLE mfi_accounting.loan_account ADD COLUMN IF NOT EXISTS dpi_suspense_amount numeric;"
        with tempfile.TemporaryDirectory() as td:
            with mock.patch.object(g, "HAND_PATCH_LOG", Path(td) / "hand.jsonl"):
                row = g.log_hand_patch(sql=sql, source="test", path="v1.sql")
        self.assertIsNotNone(row)
        self.assertIn("loan_account", row["tables"])
        self.assertIn("dpi_suspense_amount", row["columns"])

    def test_local_setup_alone_fails(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            setup = root / "scripts" / "sql" / "setup"
            setup.mkdir(parents=True)
            f = setup / "local_setup_dpi_suspense_amount.sql"
            f.write_text(
                "ALTER TABLE mfi_accounting.loan_account ADD COLUMN IF NOT EXISTS dpi_suspense_amount numeric;\n",
                encoding="utf-8",
            )
            pending = {
                "files": ["scripts/sql/setup/local_setup_dpi_suspense_amount.sql"],
                "updated_at": "2026-07-22T12:00:00Z",
                "repos": ["trustt-platform-accounting"],
            }
            with mock.patch.object(g, "ROOT", root), mock.patch.object(
                g, "INITIAL_SETUP", root / "missing-initial-setup"
            ), mock.patch.object(g, "PARITY_RESULT", root / "parity.json"), mock.patch.object(
                g, "HAND_PATCH_LOG", root / "hand.jsonl"
            ), mock.patch.object(g, "MANIFEST", g.MANIFEST):
                # money_tables still from real manifest
                r = g.check_parity(pending)
            self.assertFalse(r["ok"])
            self.assertTrue(any("not reproducible" in e for e in r["errors"]))

    def test_duplicate_versions(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            sql = root / "flyway" / "sli" / "masterdata" / "sql" / "product"
            sql.mkdir(parents=True)
            (sql / "V000119__a.sql").write_text("SELECT 1;\n", encoding="utf-8")
            (sql / "V000119__b.sql").write_text("SELECT 2;\n", encoding="utf-8")
            errs = g.find_duplicate_versions([root / "flyway" / "sli" / "masterdata" / "sql"])
            self.assertTrue(any("V000119" in e for e in errs))

    def test_hand_patch_ddl_logged(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            log = root / "hand.jsonl"
            with mock.patch.object(g, "HAND_PATCH_LOG", log), mock.patch.object(
                g, "money_tables", return_value={"loan_account"}
            ):
                row = g.log_hand_patch(
                    sql="ALTER TABLE mfi_accounting.loan_account ADD COLUMN dpi_suspense_amount numeric;",
                    source="test",
                )
            self.assertIsNotNone(row)
            self.assertIn("loan_account", row["tables"])
            # non-DDL ignored
            with mock.patch.object(g, "HAND_PATCH_LOG", log), mock.patch.object(
                g, "money_tables", return_value={"loan_account"}
            ):
                row2 = g.log_hand_patch(
                    sql="UPDATE loan_account SET loan_status='ACTIVE' WHERE id=1;",
                    source="test",
                )
            self.assertIsNone(row2)


if __name__ == "__main__":
    unittest.main()
