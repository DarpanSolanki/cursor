"""Guard the four newly-ported batch-footprint previews against the three defects prior
audits already fixed once: a shared-bean edge, a DAO resolved to the wrong entity, and a
duplicate edge (against its own preview or against what the KG already derives from source).

    python3 scripts/lib/test_batch_footprint_port.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sqlite3
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "scripts" / "scratch" / "batch-scan-port"
CURATED = ROOT / "cursor-bundle" / "kg" / "curated" / "batch_footprint.jsonl"
DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"

sys.path.insert(0, str(ROOT / "scripts" / "testing"))
from batch_footprint_scan import _SHARED_BEANS  # noqa: E402

REPOS = ("reporting", "payments", "los", "task")


def load_jsonl(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def preview_edges() -> dict[str, list[dict]]:
    return {repo: load_jsonl(SCRATCH / f"{repo}_curated_preview.jsonl") for repo in REPOS}


def all_preview_edges() -> list[dict]:
    out: list[dict] = []
    for rows in preview_edges().values():
        out.extend(rows)
    return out


def scan_rows() -> dict[str, list[dict]]:
    return {repo: load_jsonl(SCRATCH / f"{repo}_batch_footprint.jsonl") for repo in REPOS}


class NoSharedBeanTest(unittest.TestCase):
    """A shared bean run by many unrelated flows must never anchor a scanned edge."""

    def test_no_edge_attaches_to_a_shared_bean(self) -> None:
        offenders = []
        for repo, rows in preview_edges().items():
            for row in rows:
                bean = row["from"].removeprefix("processor:")
                if bean in _SHARED_BEANS:
                    offenders.append(f"{repo}: {row['from']} -> {row['to']} ({row['note']})")
        self.assertEqual([], offenders,
                          "edge(s) anchored to a cross-service shared bean:\n"
                          + "\n".join(offenders))


class DaoOwnEntityTest(unittest.TestCase):
    """Every DAO in the scan evidence must resolve to an entity that is plausibly its own,
    never the most-frequently-mentioned entity in an unrelated facade."""

    _EVIDENCE = re.compile(r"^(?P<path>.+?) -> (?P<dao>\w+) -> (?P<entity>\w+)$")

    def test_dao_resolves_to_its_own_entity(self) -> None:
        offenders = []
        for repo, rows in scan_rows().items():
            for row in rows:
                for table, evidence in row.get("evidence", {}).items():
                    m = self._EVIDENCE.match(evidence)
                    if not m:
                        continue
                    dao, entity = m.group("dao"), m.group("entity")
                    dao_base = re.sub(r"(DAOService|DaoService|Repository|Service)$", "",
                                       dao).lower()
                    entity_base = re.sub(r"(Entity|Details|History)$", "", entity).lower()
                    if dao_base and entity_base and dao_base not in entity_base \
                            and entity_base not in dao_base:
                        offenders.append(
                            f"{repo}/{row['job']}: {dao} -> {entity} (table {table}) "
                            f"— names do not overlap, suspect frequency-pick over-attribution")
        self.assertEqual([], offenders,
                          "DAO resolved to an entity its own name does not match:\n"
                          + "\n".join(offenders))


class NoDuplicateEdgeTest(unittest.TestCase):
    """No preview edge may repeat within/across the four previews, and none may already be
    derivable from source (accounting's existing curated overlay, or the live graph)."""

    def test_no_duplicate_within_or_across_previews(self) -> None:
        seen: dict[tuple, str] = {}
        dupes = []
        for repo, rows in preview_edges().items():
            for row in rows:
                key = (row["from"], row["to"], row["rel"])
                if key in seen:
                    dupes.append(f"{key} in {repo} duplicates {seen[key]}")
                else:
                    seen[key] = repo
        self.assertEqual([], dupes, "duplicate edge(s) across the four previews:\n"
                          + "\n".join(dupes))

    def test_no_duplicate_against_existing_curated_accounting_edges(self) -> None:
        existing = {(json.loads(l)["from"], json.loads(l)["to"], json.loads(l)["rel"])
                    for l in CURATED.read_text(encoding="utf-8").splitlines() if l.strip()} \
            if CURATED.is_file() else set()
        dupes = []
        for repo, rows in preview_edges().items():
            for row in rows:
                key = (row["from"], row["to"], row["rel"])
                if key in existing:
                    dupes.append(f"{repo}: {key} already in cursor-bundle/kg/curated/"
                                 "batch_footprint.jsonl")
        self.assertEqual([], dupes, "\n".join(dupes))

    def test_no_duplicate_against_source_derived_graph_edges(self) -> None:
        if not DB.is_file():
            self.skipTest("kg.db not built")
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            source_derived = {
                (f, t, r) for f, t, r in con.execute(
                    "SELECT src_id, dst_id, rel FROM edges WHERE rel IN "
                    "('reads','writes','deletes') AND src_id LIKE 'processor:%' "
                    "AND (src IS NULL OR src NOT LIKE '%batch_footprint_scan%')")
            }
        finally:
            con.close()
        dupes = []
        for repo, rows in preview_edges().items():
            for row in rows:
                key = (row["from"], row["to"], row["rel"])
                if key in source_derived:
                    dupes.append(f"{repo}: {key} already derived from source in the live graph")
        self.assertEqual([], dupes, "\n".join(dupes))


class SanityTest(unittest.TestCase):
    """The guard itself must be exercising real data, not silently skipping."""

    def test_previews_are_non_empty(self) -> None:
        for repo, rows in preview_edges().items():
            self.assertGreater(len(rows), 0, f"{repo} preview is empty — nothing to guard")


if __name__ == "__main__":
    unittest.main()
