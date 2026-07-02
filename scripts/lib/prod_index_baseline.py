#!/usr/bin/env python3
"""Load production index snapshot from cursor-bundle/reference/db/."""
from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REF_DIR = ROOT / "cursor-bundle/reference/db"
MANIFEST_PATH = REF_DIR / "prod-indexes-manifest.json"
DEFAULT_CSV = REF_DIR / "prod-indexes-baseline.csv"

COL_RE = re.compile(r"\(([^)]+)\)", re.DOTALL)


@dataclass(frozen=True)
class IndexRow:
    schemaname: str
    tablename: str
    indexname: str
    indexdef: str

    @property
    def is_primary(self) -> bool:
        return "_pkey" in self.indexname.lower() or " PRIMARY " in self.indexdef.upper()

    def column_tokens(self) -> list[str]:
        m = COL_RE.search(self.indexdef)
        if not m:
            return []
        raw = m.group(1)
        parts: list[str] = []
        for chunk in raw.split(","):
            token = chunk.strip().split()[0]
            token = token.strip('"').lower()
            if token and token not in ("hash", "asc", "desc"):
                parts.append(token)
        return parts


class ProdIndexBaseline:
    def __init__(self, csv_path: Path | None = None) -> None:
        self.csv_path = csv_path or self._resolve_csv_path()
        self.manifest = self._load_manifest()
        self.rows = self._load_rows()

    @staticmethod
    def _resolve_csv_path() -> Path:
        if MANIFEST_PATH.is_file():
            data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
            name = data.get("canonical_csv", "prod-indexes-baseline.csv")
            return REF_DIR / name
        return DEFAULT_CSV

    @staticmethod
    def _load_manifest() -> dict:
        if not MANIFEST_PATH.is_file():
            return {}
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))

    def _load_rows(self) -> list[IndexRow]:
        if not self.csv_path.is_file():
            raise FileNotFoundError(f"Prod index baseline missing: {self.csv_path}")
        rows: list[IndexRow] = []
        with self.csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                rows.append(
                    IndexRow(
                        schemaname=row["schemaname"].strip(),
                        tablename=row["tablename"].strip(),
                        indexname=row["indexname"].strip(),
                        indexdef=row.get("indexdef", "").strip(),
                    )
                )
        return rows

    @property
    def snapshot_date(self) -> str:
        return str(self.manifest.get("snapshot_date", "unknown"))

    def for_table(self, schema: str, table: str) -> list[IndexRow]:
        schema, table = schema.lower(), table.lower()
        return [r for r in self.rows if r.schemaname == schema and r.tablename == table]

    def index_names(self, schema: str, table: str) -> set[str]:
        return {r.indexname for r in self.for_table(schema, table)}

    def secondary_indexes(self, schema: str, table: str) -> list[IndexRow]:
        return [r for r in self.for_table(schema, table) if not r.is_primary]

    def has_index(self, schema: str, table: str, index_name: str) -> bool:
        return index_name in self.index_names(schema, table)

    def covers_columns(self, schema: str, table: str, columns: list[str]) -> list[IndexRow]:
        want = {c.lower() for c in columns}
        hits: list[IndexRow] = []
        for idx in self.secondary_indexes(schema, table):
            cols = set(idx.column_tokens())
            if want & cols:
                hits.append(idx)
        return hits

    def missing_from_prod(self, schema: str, table: str, expected_names: list[str]) -> list[str]:
        present = self.index_names(schema, table)
        return [n for n in expected_names if n not in present]

    def format_table_report(self, schema: str, table: str) -> str:
        rows = self.for_table(schema, table)
        lines = [
            f"Prod index baseline ({self.snapshot_date}): {schema}.{table} — {len(rows)} index(es)",
        ]
        for r in rows:
            kind = "PK" if r.is_primary else "secondary"
            cols = ", ".join(r.column_tokens()) or "?"
            lines.append(f"  [{kind}] {r.indexname} ({cols})")
        if not rows:
            lines.append("  (no indexes in baseline — table may be absent from snapshot)")
        return "\n".join(lines)
