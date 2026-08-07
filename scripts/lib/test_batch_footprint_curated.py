"""Guard the three defects the batch-footprint curated overlay must never reintroduce.

`scripts/testing/batch_footprint_scan.py --repo <r> --curated-preview` writes
`scripts/scratch/batch-scan-port/<r>_curated_preview.jsonl` for reporting, payments, los and
task without touching the tracked KG overlay. This checks that preview output — and, once
emitted, `cursor-bundle/kg/curated/batch_footprint.jsonl` — against the three defects an
earlier version of the scanner shipped:

  1. an edge attached to a bean shared across services (`_SHARED_BEANS`)
  2. a DAO resolved to a co-mentioned entity instead of its own, when its own is present
  3. a duplicate edge, either within/across the preview files or against an edge the KG
     already derives from source

A failure here means the SCANNER has a defect — fix `batch_footprint_scan.py` and
regenerate the previews; do not edit the jsonl output or filter the symptom out here.

    python3 scripts/lib/test_batch_footprint_curated.py
"""
from __future__ import annotations

import collections
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

import batch_footprint_scan as bfs  # noqa: E402

PREVIEW_REPOS = {
    "reporting": "trustt-platform-reporting",
    "payments": "trustt-platform-payments",
    "los": "trustt-platform-los",
    "task": "trustt-platform-task",
}


def load_edges(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def all_preview_edges() -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for repo_key in PREVIEW_REPOS:
        out[repo_key] = load_edges(SCRATCH / f"{repo_key}_curated_preview.jsonl")
    return out


class SharedBeanTest(unittest.TestCase):
    """Defect 1: no edge may attach to a bean that runs across unrelated services."""

    def test_no_preview_edge_attaches_to_a_shared_bean(self) -> None:
        offenders = []
        for repo_key, edges in all_preview_edges().items():
            for e in edges:
                bean = e["from"].removeprefix("processor:")
                if bean in bfs._SHARED_BEANS:
                    offenders.append((repo_key, e["from"], e["to"]))
        self.assertFalse(
            offenders,
            "edge(s) attached to a shared bean (_SHARED_BEANS) — this is the "
            f"populateUserDetails-class over-attribution defect: {offenders}")

    def test_curated_overlay_itself_has_no_shared_bean_edge(self) -> None:
        offenders = []
        for e in load_edges(CURATED):
            bean = e["from"].removeprefix("processor:")
            if bean in bfs._SHARED_BEANS:
                offenders.append((e["from"], e["to"]))
        self.assertFalse(offenders, f"tracked curated overlay has shared-bean edges: {offenders}")


class DaoOwnEntityTest(unittest.TestCase):
    """Defect 2: a DAO must resolve to its own entity when one is mentioned in its source,
    never to whichever entity it happens to mention most often (InterestSetupDAOService ->
    interest_setup, not interest_setup_date_slab)."""

    def test_dao_to_entity_prefers_own_name_over_frequency_for_every_repo(self) -> None:
        offenders = []
        for repo_key, repo_dir in PREVIEW_REPOS.items():
            java_root = ROOT / repo_dir / "src" / "main" / "java"
            if not java_root.is_dir():
                continue
            resolved = bfs.dao_to_entity(java_root)
            for path in java_root.rglob("*.java"):
                stem = path.stem
                if not stem.endswith(("DAOService", "DaoService", "Repository", "Service")):
                    continue
                if bfs._CONFIG_WIRING.search(stem):
                    continue
                if stem not in resolved:
                    continue
                try:
                    text = path.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                names = collections.Counter(bfs._ENTITY_REF.findall(text))
                base = (stem.replace("DAOService", "").replace("DaoService", "")
                            .replace("Repository", "").replace("Service", "").lower())
                own_matches = {n for n in names if n != stem
                               and n.lower().rstrip("entity") == base}
                if not own_matches:
                    continue
                chosen = resolved[stem]
                if chosen not in own_matches:
                    most_common = names.most_common(1)[0][0] if names else None
                    offenders.append((repo_key, stem, chosen, sorted(own_matches), most_common))
        self.assertFalse(
            offenders,
            "DAO(s) resolved away from their own entity despite one being present "
            f"(repo, dao, chosen, own_matches, most_common): {offenders}")

    def test_no_config_wiring_class_leaked_into_the_dao_map(self) -> None:
        offenders = []
        for repo_key, repo_dir in PREVIEW_REPOS.items():
            java_root = ROOT / repo_dir / "src" / "main" / "java"
            if not java_root.is_dir():
                continue
            for stem in bfs.dao_to_entity(java_root):
                if bfs._CONFIG_WIRING.search(stem):
                    offenders.append((repo_key, stem))
        self.assertFalse(offenders, f"*ConfigService wiring class(es) leaked as a DAO: {offenders}")


class NoDuplicateEdgeTest(unittest.TestCase):
    """Defect 3: build.sh does not dedup — the scanner must never emit a duplicate itself,
    whether against its own other rows or against an edge the KG already derives from source."""

    def test_no_duplicate_within_a_single_preview_file(self) -> None:
        for repo_key, edges in all_preview_edges().items():
            keys = [(e["from"], e["to"], e["rel"]) for e in edges]
            counts = collections.Counter(keys)
            dupes = [k for k, n in counts.items() if n > 1]
            self.assertFalse(dupes, f"{repo_key}: duplicate edge(s) within its own preview file: {dupes}")

    def test_no_duplicate_across_the_four_preview_files(self) -> None:
        seen: dict[tuple, str] = {}
        offenders = []
        for repo_key, edges in all_preview_edges().items():
            for e in edges:
                key = (e["from"], e["to"], e["rel"])
                if key in seen and seen[key] != repo_key:
                    offenders.append((key, seen[key], repo_key))
                else:
                    seen.setdefault(key, repo_key)
        self.assertFalse(offenders, f"same edge emitted by more than one repo's scan: {offenders}")

    def test_no_duplicate_against_edges_the_kg_already_derives_from_source(self) -> None:
        if not DB.is_file():
            self.skipTest("kg.db not built")
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        try:
            existing = set(con.execute(
                "SELECT src_id, dst_id, rel FROM edges WHERE rel IN ('reads','writes','deletes') "
                "AND src_id LIKE 'processor:%' "
                "AND (src IS NULL OR src NOT LIKE '%batch_footprint_scan%')"))
        finally:
            con.close()
        offenders = []
        for repo_key, edges in all_preview_edges().items():
            for e in edges:
                key = (e["from"], e["to"], e["rel"])
                if key in existing:
                    offenders.append((repo_key, key))
        self.assertFalse(
            offenders,
            f"preview edge duplicates a source-derived edge already in the KG: {offenders}")

    def test_new_repo_edges_appear_at_most_once_in_tracked_overlay(self) -> None:
        """Scoped to the edges the four new repos contribute — accounting's existing block is
        emitted by a separate, pre-existing path this task does not touch or regenerate, and
        may carry its own history independent of this scan."""
        counts = collections.Counter((e["from"], e["to"], e["rel"]) for e in load_edges(CURATED))
        combined_new = {(e["from"], e["to"], e["rel"])
                         for edges in all_preview_edges().values() for e in edges}
        offenders = [k for k in combined_new if counts.get(k, 0) > 1]
        self.assertFalse(
            offenders,
            f"new-repo edge appears more than once in the tracked overlay: {offenders}")


class PreviewSanityTest(unittest.TestCase):
    """The previews must exist and be non-trivial before anything downstream trusts them."""

    def test_all_four_previews_exist_and_are_non_empty(self) -> None:
        missing = [k for k, v in all_preview_edges().items() if not v]
        self.assertFalse(missing, f"empty/missing preview for: {missing} — regenerate with "
                          "--curated-preview before running this gate")

    def test_every_edge_has_the_scanner_as_its_src(self) -> None:
        offenders = []
        for repo_key, edges in all_preview_edges().items():
            for e in edges:
                if "batch_footprint_scan" not in e.get("src", ""):
                    offenders.append((repo_key, e))
        self.assertFalse(offenders, f"edge(s) missing scanner provenance: {offenders}")


if __name__ == "__main__":
    unittest.main()
