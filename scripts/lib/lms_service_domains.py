#!/usr/bin/env python3
"""LMS-wide service domain detection — mandatory impact cases for non-money repos."""
from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from accounting_flow_domains import _path_hint_matches  # noqa: E402

DOMAIN_FILE = Path(__file__).with_name("lms_service_domains.json")


@lru_cache(maxsize=1)
def load_service_domains() -> dict:
    if not DOMAIN_FILE.is_file():
        return {}
    return json.loads(DOMAIN_FILE.read_text(encoding="utf-8")).get("services") or {}


def detect_service_domains(paths: list[str] | None, blob: str | None = None) -> list[str]:
    """Return service ids touched by changed paths (repo / path hints)."""
    paths = paths or []
    low_paths = [p.replace("\\", "/").lower() for p in paths]
    joined = blob if blob is not None else " ".join(low_paths)
    hit: list[str] = []
    for sid, meta in load_service_domains().items():
        repos = [h.lower() for h in (meta.get("repo_hints") or [])]
        phints = [h.lower() for h in (meta.get("path_hints") or [])]
        matched = False
        for p in low_paths:
            if any(_path_hint_matches(r, p) for r in repos):
                matched = True
                break
            if any(_path_hint_matches(h, p) for h in phints):
                matched = True
                break
        if not matched and joined:
            if any(_path_hint_matches(r, joined) for r in repos) or any(
                _path_hint_matches(h, joined) for h in phints
            ):
                matched = True
        if matched:
            hit.append(sid)
    return hit


def resolve_lms_service_cases(
    paths: list[str] | None,
    base: list[str],
    *,
    reg: dict,
) -> tuple[list[str], list[str]]:
    """Merge service-domain impact_cases into base; return (merged, added)."""
    domains = detect_service_domains(paths)
    if not domains:
        return list(base), []

    def add(cid: str, out: list[str]) -> None:
        if not cid or cid in out:
            return
        meta = reg.get(cid) or {}
        if meta.get("quarantine"):
            return
        if cid not in reg:
            return
        out.append(cid)

    merged = list(base)
    added: list[str] = []
    for sid in domains:
        meta = load_service_domains().get(sid) or {}
        before = len(merged)
        for cid in meta.get("impact_cases") or []:
            add(cid, merged)
        if len(merged) == before:
            fb = meta.get("fallback_case")
            if fb:
                add(fb, merged)
        for cid in merged[before:]:
            if cid not in added:
                added.append(cid)
    return merged, added
