#!/usr/bin/env python3
"""
build_batch_loaders.py — index *JobLoader.java registration order as `next` edges.

Loader.initJobs → *JobLoader.loadJobs → ConfigService.buildJobForTenant defines
EOD/BOD job pipelines not visible in orchestration XML.
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

from _paths import WORKSPACE

JOB_NAME_USE = re.compile(r"(\w+ConfigService)\.JOB_NAME")
BUILD_JOB = re.compile(r"(\w+ConfigService)\.buildJobForTenant\s*\(")


def emit(o: dict) -> None:
    sys.stdout.write(json.dumps(o, ensure_ascii=False) + "\n")


def job_name_from_config(java_path: str, config_class: str) -> str | None:
    """Resolve JOB_NAME from *ConfigService.java adjacent to loader."""
    base = os.path.dirname(java_path)
    for _ in range(8):
        for pattern in (
            os.path.join(base, f"{config_class}.java"),
            os.path.join(base, "**", f"{config_class}.java"),
        ):
            for cp in glob.glob(pattern, recursive=True):
                try:
                    text = open(cp, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                m = re.search(r'JOB_NAME\s*=\s*"([^"]+)"', text)
                if m:
                    return m.group(1)
        parent = os.path.dirname(base)
        if parent == base:
            break
        base = parent
    return None


def parse_loader(path: str) -> list[str]:
    try:
        text = open(path, encoding="utf-8", errors="replace").read()
    except OSError:
        return []
    jobs: list[str] = []
    seen: set[str] = set()
    for m in JOB_NAME_USE.finditer(text):
        jn = job_name_from_config(path, m.group(1))
        if jn and jn not in seen:
            seen.add(jn)
            jobs.append(jn)
    if jobs:
        return jobs
    for m in BUILD_JOB.finditer(text):
        jn = job_name_from_config(path, m.group(1))
        if jn and jn not in seen:
            seen.add(jn)
            jobs.append(jn)
    return jobs


def repo_name(path: str) -> str:
    parts = os.path.abspath(path).split(os.sep)
    for seg in parts:
        if seg.startswith("novopay-") or seg.startswith("trustt-"):
            return seg
    return "unknown"


def main() -> None:
    for repo in sorted(os.listdir(WORKSPACE)):
        if not (repo.startswith("novopay-") or repo.startswith("trustt-")):
            continue
        repo_dir = os.path.join(WORKSPACE, repo)
        if not os.path.isdir(os.path.join(repo_dir, "src", "main", "java")):
            continue
        for path in glob.glob(os.path.join(repo_dir, "**", "*JobLoader.java"), recursive=True):
            if "/test/" in path.replace("\\", "/"):
                continue
            jobs = parse_loader(path)
            if len(jobs) < 2:
                continue
            rel = os.path.relpath(path, WORKSPACE)
            loader_id = f"batch_loader:{os.path.splitext(os.path.basename(path))[0]}"
            emit({
                "t": "node",
                "id": loader_id,
                "kind": "batch_loader",
                "label": os.path.basename(path),
                "repo": repo_name(path),
                "role": "spring_batch_loader",
                "src": rel,
            })
            for i, job in enumerate(jobs):
                emit({
                    "t": "edge",
                    "from": loader_id,
                    "to": f"request:{job}",
                    "rel": "registers",
                    "seq": i + 1,
                    "src": rel,
                })
                emit({
                    "t": "edge",
                    "from": f"batch_job:{repo}:{job}",
                    "to": f"request:{job}",
                    "rel": "triggers",
                    "src": rel,
                })
            for i in range(len(jobs) - 1):
                emit({
                    "t": "edge",
                    "from": f"request:{jobs[i]}",
                    "to": f"request:{jobs[i + 1]}",
                    "rel": "next",
                    "note": f"{os.path.basename(path)} registration order",
                    "src": rel,
                })


if __name__ == "__main__":
    main()
