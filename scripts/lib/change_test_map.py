#!/usr/bin/env python3
"""Load change→api map + resolve batch class stems to known registry apiNames."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP_FILE = Path(__file__).with_name("change_test_map.json")
REGISTRY = ROOT / "scripts/testing/registry.json"

_STRIP_SUFFIXES = (
    "ItemWriter",
    "BatchService",
    "BatchProcessor",
    "ConfigService",
    "Writer",
    "Reader",
    "Processor",
)


@lru_cache(maxsize=1)
def load_map() -> dict:
    if not MAP_FILE.is_file():
        return {}
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def known_batch_apis() -> dict[str, str]:
    """apiName → registry case id for batch.* (and cases with batch_job_name)."""
    if not REGISTRY.is_file():
        return {}
    reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    out: dict[str, str] = {}
    for cid, meta in reg.items():
        if cid.startswith("_") or not isinstance(meta, dict):
            continue
        api = meta.get("api") or meta.get("batch_job_name")
        if not api:
            continue
        if cid.startswith("batch.") or meta.get("batch_job_name"):
            out[str(api)] = cid
    return out


def api_from_class_stem(stem: str) -> str | None:
    """Map Java class stem → registry apiName. Never invent raw stem as api."""
    if not stem:
        return None
    data = load_map()
    explicit = (data.get("class_to_api") or {}).get(stem)
    if explicit:
        return explicit

    known = known_batch_apis()
    known_l = {a.lower(): a for a in known}

    base = stem
    for suf in _STRIP_SUFFIXES:
        if base.endswith(suf) and len(base) > len(suf):
            base = base[: -len(suf)]
            break
    if not base:
        return None
    camel = base[0].lower() + base[1:]
    for cand in (camel, camel + "Job", camel + "BatchApi"):
        if cand in known:
            return cand
        if cand.lower() in known_l:
            return known_l[cand.lower()]
    # Booking → Posting alias when only posting exists in registry
    if camel.endswith("Booking"):
        posting = camel[: -len("Booking")] + "Posting"
        if posting in known:
            return posting
        if posting.lower() in known_l:
            return known_l[posting.lower()]
    return None


def api_from_path(path: str) -> str | None:
    s = path.replace("\\", "/").lower()
    for needle, api in load_map().get("path_to_api") or []:
        if needle.lower() in s:
            return api
    return None
